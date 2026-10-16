#!/usr/bin/env python3
"""handoff_codegen.py — codegen del gate G3 (handoff) de MALGAMES/PONG_V0.

Que agrega sobre `pong_codegen.py`
---------------------------------
`pong_codegen.py` instala en el generador upstream una tabla opcode -> '0'/'1' y obtiene
un dispatch cuya SALIDA es el bit del predicado en ASCII. Eso resuelve UNA ejecucion. El
gate G3 pide algo que ninguna evidencia de MALDOOM ni de MALGAMES tiene: que una segunda
ejecucion **lea** el byte que la primera imprimio, sin que el host lo re-codifique entre
ambas. Para eso hace falta un alfabeto de handoff y aqui caen dos hechos medidos:

    1. La cadena de discriminacion de upstream prueba `t = k - 2`, es decir solo valores
       CONTIGUOS 0..M-1. Con el tope real de rutas (26, ver README "tope medido del kernel")
       el mayor valor discriminable es 25. El ASCII '0'/'1' son 48/49: un dispatch que los
       discriminate necesita >= 50 rutas ~= 90 241 B > 59 049 celdas. Descartado por medida
       (anclajes reales: 24 rutas = 56 361 B, 32 rutas = rc 1 "Free space exceeded").
    2. El alfabeto 0x00 esta ocupado: `dispatch_00` es HALT sin salida, asi que un byte 0
       en stdin del receptor es una orden de parada, no un dato.

    => el alfabeto de handoff es {0x01, 0x02}, y se produce con constantes DECIMALES de
       HeLL: medido sobre el despacho de 3 rutas, `ROT (1 << 1)` emite 0x01 y
       `ROT (0t2 << 1)` emite 0x02. Los literales de caracter de HeLL NO sirven: el patron
       `chr` del lexer solo cubre 0x20..0x7E, ningun byte de control es escribible.

Dos artefactos nuevos
---------------------
    A-raw  = mismo predicado bounce, mismas 8 rutas, PERO cada ruta emite el byte CRUDO
             0x01 (bit 1) o 0x02 (bit 0) en vez de la letra ASCII.
    B-NOTA = dispatch de 3 opcodes [00, 01, 02]: al recibir 0x01 emite '0', al recibir
             0x02 emite '1', 0x00 es HALT, cualquier otro byte cae al fallback de upstream
             (eco). Es decir B calcula NOT sobre el bit que le llega por stdin.

Upstream se abre SOLO en lectura y se re-verifica su SHA-256 al final de cada emision.
El `.mb` sellado de G2 no se toca, no se renombra y no se regenera: A-raw es un artefacto
NUEVO aparte, con su propio hash.

Modos
-----
    handoff_codegen.py emit-a-raw  -o OUT.hell [--kind bounce]
    handoff_codegen.py emit-b      -o OUT.hell [--variant nota|swap]
    handoff_codegen.py expect                          > tabla NOT(bounce) derivada del oraculo
Salida: LF exclusivo, sin CR, sin BOM. Entrada invalida: stderr + exit != 0 + cero stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import pong_codegen as cg                                # noqa: E402

UPSTREAM = cg.UPSTREAM

# alfabeto de handoff: 0x00 queda reservado (dispatch_00 = HALT sin salida)
RAW_FOR_BIT = {1: 1, 0: 2}
RAW_MIN, RAW_MAX = 0x01, 0x02

# presupuesto medido del generador: 25091 B + 1303 B/ruta, tope 59049 celdas
CELLS_CLASSIC = 3 ** 10
SIZE_FIT_INTERCEPT = 25091
SIZE_FIT_SLOPE = 1303
MAX_ROUTES = (CELLS_CLASSIC - SIZE_FIT_INTERCEPT) // SIZE_FIT_SLOPE   # 26
MAX_DISCRIMINABLE_VALUE = MAX_ROUTES - 1                               # 25

_ROT_LINE = re.compile(r"^\tROT \('(.)' << 1\) R_ROT$")
_LABEL_LINE = re.compile(r"^dispatch_([0-9a-f]{2}):$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite_raw_markers(text: str, expect_routes: int) -> tuple[str, int]:
    """Cada `ROT ('c' << 1)` de una ruta `dispatch_XX` pasa a `ROT (n << 1)` con n crudo.

    Se reescribe por ETIQUETA, no por caracter, porque varias rutas comparten el mismo
    marcador imprimible. Deva (texto, numero_de_rutas_reescritas).
    """
    lines = text.split("\n")
    out: list[str] = []
    cur: int | None = None
    n = 0
    for ln in lines:
        m = _LABEL_LINE.match(ln)
        if m:
            cur = int(m.group(1), 16)
            out.append(ln)
            continue
        m2 = _ROT_LINE.match(ln)
        if m2 and cur not in (None, 0):
            bit = int(m2.group(1))
            if bit not in RAW_FOR_BIT:
                raise SystemExit(f"marcador no binario en dispatch_{cur:02x}: {m2.group(1)!r}")
            out.append("\tROT (%d << 1) R_ROT" % RAW_FOR_BIT[bit])
            n += 1
            cur = None
            continue
        if not m2:
            cur = None
        out.append(ln)
    if n != expect_routes:
        raise SystemExit(f"reescritura raw incompleta: {n} rutas, se esperaban {expect_routes}")
    return "\n".join(out), n


def emit_a_raw(kind: str) -> tuple[str, int]:
    """A-raw: mismo despacho que `pong_codegen.emit_hell`, salida en bytes crudos."""
    text = cg.emit_hell(kind)                     # re-verifica el sha de upstream por dentro
    rewritten, n = rewrite_raw_markers(text, len(cg.domain(kind)))
    return rewritten, n


def emit_b(variant: str) -> str:
    """B: dispatch de 3 rutas sobre el alfabeto de handoff."""
    mod = cg.load_upstream()
    if variant == "eco":
        # SIN parchar MARKERS: salida intacta de upstream (0x01->'P', 0x02->'R'). Lo que hace
        # el trabajo es el fallback, que no depende de la tabla: recibe 0x30/0x31 del A sellado,
        # ningun opcode coincide, y el fallback emite el byte VERBATIM.
        text = mod.generate([0x00, 0x01, 0x02], push_const_out=False)
    else:
        tables = {
            "nota": {0x01: "0", 0x02: "1"},           # niega el bit recibido
            "swap": {0x01: "1", 0x02: "0"},           # mutante de control: NO niega
        }
        table = tables[variant]
        ops = [0x00, 0x01, 0x02]
        assert set(table) == set(ops[1:]), "B debe cubrir exactamente 0x01 y 0x02"
        mod.MARKERS = table
        text = mod.generate(ops, push_const_out=False)
    now = sha256(UPSTREAM)
    if now != mod._qoder_pristine_sha:
        raise SystemExit(f"ALERTA: el fuente upstream cambio durante la ejecucion: {now}")
    return text


def expect_composition(kind: str, negate: bool = True) -> dict[int, str]:
    """bounce (o NOT(bounce)) derivado del ORACULO, por via INDEPENDIENTE del host.

    El host no re-codifica nada aqui: se construye el estado del spec, se llama a
    `oracle/pong_reference.step` y se lee si `vy` cambio (eso ES el rebote segun par. 4).
    """
    sys.path.insert(0, str(cg.REPO / "oracle"))
    import pong_reference as ref

    table = {}
    for op, _ in cg.domain(kind):
        if kind == "bounce":
            by, vy = cg.decode_bounce(op)
            state = (cg.BOARD_W, cg.BOARD_H, 4, by, 1, vy, 0, 0, 0, 0, 0)
            out = ref.step(state, 0, 0)
            bounce = 1 if out[5] != vy else 0
        elif kind == "contact":
            pl, by = cg.decode_contact(op)
            vy = -1 if by == 0 else 1
            out = ref.step((cg.BOARD_W, cg.BOARD_H, 0, by - vy, -1, vy, pl, 0, 0, 0, 0), 0, 0)
            bounce = 1 if (out[2] == 0 and out[4] == 1) else 0
        else:
            raise ValueError(f"kind desconocido: {kind}")
        table[op] = str((1 - bounce) if negate else bounce)
    return table


def header_a_raw(kind: str) -> str:
    table = cg.marker_table(kind)
    exp = expect_composition(kind)
    lines = [f"/* MALGAMES/vm/classic A-raw — predicado `{kind}` de G2, re-emitido en el",
             f" * alfabeto de handoff {{0x01, 0x02}} en lugar de ASCII '0'/'1'.",
             f" * Motivo (medido): la cadena de despacho de upstream solo discrimina valores",
             f" * contiguos 0..M-1 con M <= {MAX_ROUTES} rutas ({CELLS_CLASSIC} celdas), asi que",
             f" * 48/49 son inalcanzables; 0x00 es HALT sin salida y por eso esta reservado.",
             f" * Produccion (medida): `ROT (1 << 1)` emite 0x01, `ROT (2 << 1)` emite 0x02.",
             f" * Each route (bit -> raw byte) y lo que debe calcular la cadena A-raw | B-NOTA:",
             ]
    for op in sorted(table):
        if kind == "bounce":
            a, b = cg.decode_bounce(op)
            coords = f"by={a}, vy={b:+d}"
        else:
            a, b = cg.decode_contact(op)
            coords = f"pl={a}, by={b}"
        lines.append(f" *   0x{op:02x}  {coords:16} bounce={table[op]}  A-raw->0x{RAW_FOR_BIT[int(table[op])]:02x}"
                     f"  B-NOTA->'{exp[op]}'")
    lines.append(" * Un byte de entrada, un byte de salida, despues HALT. No es un tick completo.")
    lines.append(" */")
    return "\n".join(lines) + "\n"


def header_b(variant: str) -> str:
    if variant == "eco":
        return ("/* MALGAMES/vm/classic B-ECO — receptor del handoff con el productor SELLADO.\n"
                " * Salida INTACTA de `mbir_dispatch_gen.py --opcodes 000102` (sin parchar MARKERS):\n"
                " *   0x01 -> 'P'   0x02 -> 'R'   0x00 -> HALT sin salida   otro -> ECO verbatim\n"
                " * Aqui lo que ejecuta el edge es la ULTIMA rama: del A sellado llegan 0x30/0x31,\n"
                " * ningun opcode coincide, y el fallback imprime el byte recibido tal cual. No se\n"
                " * calcula un NOT: se demuestra que el byte del artefacto sellado ya viaja.\n */\n")
    desc = {"nota": "NIEGA el bit recibido por stdin",
            "swap": "MUTANTE de selectividad: re-echoea el bit sin negarlo"}[variant]
    return ("/* MALGAMES/vm/classic B-NOTA — receptor del handoff G3 (%s).\n"
            " * Dispatch de 3 rutas sobre el alfabeto de handoff:\n"
            " *   0x01 -> '%s'   0x02 -> '%s'   0x00 -> HALT sin salida\n"
            " * Cualquier otro byte cae al fallback de upstream (eco verbatim), lo que hace\n"
            " * visible que la ruta del NOT se ejecuto y no el eco.\n */\n"
            % (desc, {"nota": "0", "swap": "1"}[variant], {"nota": "1", "swap": "0"}[variant]))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("mode", choices=["emit-a-raw", "emit-b", "expect"])
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--kind", default="bounce", choices=list(cg.KINDS))
    ap.add_argument("--variant", default="nota", choices=["nota", "swap", "eco"])
    a = ap.parse_args(argv[1:])

    try:
        if a.mode == "expect":
            exp = expect_composition(a.kind)
            for op in sorted(exp):
                sys.stdout.write(f"{op:02x} {exp[op]}\n")
            return 0
        if a.mode == "emit-a-raw":
            body, n = emit_a_raw(a.kind)
            text = header_a_raw(a.kind) + body
        elif a.mode == "emit-b":
            text = header_b(a.variant) + emit_b(a.variant)
        else:
            return 2
        if a.out:
            Path(a.out).write_text(text, encoding="utf-8", newline="\n")
            etiqueta = f"variant={a.variant}" if a.mode == "emit-b" else f"kind={a.kind}"
            print(f"escribio {a.out} ({len(text.encode())} bytes, {etiqueta})")
        else:
            sys.stdout.write(text)
        return 0
    except (ValueError, IndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except AssertionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
