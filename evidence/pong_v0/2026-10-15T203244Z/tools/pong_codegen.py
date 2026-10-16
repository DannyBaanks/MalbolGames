#!/usr/bin/env python3
"""pong_codegen.py — extension del codegen HeLL -> Malbolge Clasico para MALGAMES/PONG_V0.

Que agrega sobre la herramienta upstream
----------------------------------------
`MALBOLGE-MB-DATABASE/vm_malbolge/tools/mbir_dispatch_gen.py` emite un dispatch N-way
de un byte y fija en el modulo la tabla `MARKERS = {0x01:"P", 0x02:"R", ...}`: cada ruta
imprime una letra arbitraria. Esa tabla NO es parametrizable por CLI. Para calcular un
predicado de Pong dentro de la VM hace falta que cada ruta imprima `'0'` o `'1'`, es
decir la salida del predicado. Este script hace exactamente esa extension:

    1. define el dominio finito del predicado (tablero 8x4),
    2. deriva la tabla opcode -> '0'/'1' desde la especificacion (no a mano),
    3. instala esa tabla en el modulo upstream en memoria y llama a su `generate()`.

Upstream se abre SOLO en lectura: este script nunca escribe dentro de
`MALBOLGE-MB-DATABASE` y re-verifica al final que el SHA-256 del fuente upstream no
cambio (prueba de no mutacion de herramienta compartida).

Que NO hace
-----------
El dispatch clasifica por VALOR usando aritmetica ternaria real (increment/decrement con
carry, ver el idioma digital_root de upstream), pero la etiqueta que imprime cada ruta es
una constante horneada en tiempo de codegen. Por tanto esto demuestra la funcion
`predicado: dominio_finito -> {0,1}` evaluada dentro de la VM sobre una codificacion que
el host ya eligio. NO demuestra aritmetica general en VM, ni un tick completo, y mucho
menos un juego.

Modos
-----
    pong_codegen.py encode   <by> <vy>                 > 0x opcode (una linea hex)
    pong_codegen.py expect   <opcode_hex>              > '0'|'1' segun la tabla derivada
    pong_codegen.py emit     -o OUT.hell [--kind KIND] > escribe el fuente HeLL
    pong_codegen.py check                              > contrasta la tabla contra el
                                                        oraculo `oracle/pong_reference.py`
Salida: LF exclusivo, sin CR, sin BOM. Entrada invalida: stderr + exit != 0 + cero bytes
en stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]                       # MALGAMES/
UPSTREAM = REPO.parent / "MALBOLGE-MB-DATABASE" / "vm_malbolge" / "tools" / "mbir_dispatch_gen.py"

# --- dominio del predicado: tablero 8x4, congelado por docs/PONG_MIN_SPEC.md par. 1/4 ---
BOARD_W = 8
BOARD_H = 4

KINDS = ("bounce", "contact")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_upstream():
    if not UPSTREAM.is_file():
        raise SystemExit(f"herramienta upstream no encontrada: {UPSTREAM}")
    before = sha256(UPSTREAM)
    spec = importlib.util.spec_from_file_location("mbir_dispatch_gen_upstream", UPSTREAM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._qoder_pristine_sha = before
    return mod


# ---------------------------------------------------------------------------- encoding ---
def encode_bounce(by: int, vy: int) -> int:
    """(by, vy) -> opcode 0x01..0x08. by en 0..BOARD_H-1, vy en {-1,+1}."""
    if not 0 <= by <= BOARD_H - 1:
        raise ValueError(f"by fuera de 0..{BOARD_H - 1}: {by}")
    if vy not in (-1, 1):
        raise ValueError(f"vy debe ser -1 o +1: {vy}")
    return 1 + by * 2 + (0 if vy == -1 else 1)


def decode_bounce(op: int) -> tuple[int, int]:
    if not 1 <= op <= 2 * BOARD_H:
        raise ValueError(f"opcode fuera de 0x01..0x{2 * BOARD_H:02x}: {op:#04x}")
    k = op - 1
    return k // 2, (-1 if k % 2 == 0 else 1)


def bounce_vertical(by: int, vy: int) -> int:
    """docs/PONG_MIN_SPEC.md par. 4, rama vertical: rebota IFF by+vy sale del tablero."""
    ny = by + vy
    return 1 if (ny < 0 or ny > BOARD_H - 1) else 0


def encode_contact(pl: int, by: int) -> int:
    """(pl, by) -> opcode 0x01..0x10.

    `pl` es la fila de la paleta IZQUIERDA ya clampeada y `by` la fila de la pelota
    DESPUES del eje vertical: docs/PONG_MIN_SPEC.md par. 4 ordena tick -> paletas ->
    vertical -> horizontal, asi que la puerta de gol lee esos dos valores derivados.
    """
    if not 0 <= pl <= BOARD_H - 1:
        raise ValueError(f"pl fuera de 0..{BOARD_H - 1}: {pl}")
    if not 0 <= by <= BOARD_H - 1:
        raise ValueError(f"by fuera de 0..{BOARD_H - 1}: {by}")
    return 1 + pl * BOARD_H + by


def decode_contact(op: int) -> tuple[int, int]:
    if not 1 <= op <= BOARD_H * BOARD_H:
        raise ValueError(f"opcode fuera de 0x01..0x{BOARD_H * BOARD_H:02x}: {op:#04x}")
    k = op - 1
    return k // BOARD_H, k % BOARD_H


def contact_gate(pl: int, by: int) -> int:
    """El gol se convierte en golpe IFF la paleta esta en la fila post-vertical (par. 4)."""
    return 1 if pl == by else 0


def domain(kind: str):
    if kind == "bounce":
        return [(encode_bounce(by, vy), bounce_vertical(by, vy))
                for by in range(BOARD_H) for vy in (-1, 1)]
    if kind == "contact":
        return [(encode_contact(pl, by), contact_gate(pl, by))
                for pl in range(BOARD_H) for by in range(BOARD_H)]
    raise ValueError(f"kind desconocido: {kind}")


def marker_table(kind: str) -> dict[int, str]:
    return {op: ("1" if bit else "0") for op, bit in domain(kind)}


def opcode_list(kind: str) -> list[int]:
    return [0x00] + sorted(op for op, _ in domain(kind))


# --------------------------------------------------------------------------------- emit ---
def emit_hell(kind: str) -> str:
    mod = load_upstream()
    ops = opcode_list(kind)
    table = marker_table(kind)
    assert set(table) == set(ops[1:]), "la tabla de marcadores no cubre exactamente las rutas"
    mod.MARKERS = table                       # <-- la extension: opcode -> '0'/'1'
    text = mod.generate(ops, push_const_out=False)
    now = sha256(UPSTREAM)
    if now != mod._qoder_pristine_sha:
        raise SystemExit(f"ALERTA: el fuente upstream cambio durante la ejecucion: {now}")
    return text


def header_block(kind: str) -> str:
    table = marker_table(kind)
    lines = [f"/* MALGAMES/vm/classic codegen - predicado `{kind}` sobre tablero "
             f"{BOARD_W}x{BOARD_H}, dominio finito de {len(table)} puntos.",
             " * Codificacion y salida de cada ruta (derivada de docs/PONG_MIN_SPEC.md par. 4):"]
    for op in sorted(table):
        if kind == "bounce":
            a, b = decode_bounce(op)
            lines.append(f" *   0x{op:02x}  by={a}, vy={b:+d}   -> '{table[op]}'")
        else:
            a, b = decode_contact(op)
            lines.append(f" *   0x{op:02x}  pl={a}, by={b}  -> '{table[op]}'")
    lines.append(" * Un solo byte de entrada, un solo byte de salida, despues HALT.")
    lines.append(" * No es un tick completo: UN predicado sobre un dominio finito.")
    lines.append(" */")
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------------------- check ---
def check(kind: str) -> int:
    """Contrasta la tabla derivada contra el oraculo, por una via INDEPENDIENTE del host."""
    sys.path.insert(0, str(REPO / "oracle"))
    import pong_reference as ref

    fallos = 0
    table = marker_table(kind)
    if kind == "bounce":
        for op in sorted(table):
            by, vy = decode_bounce(op)
            # estado interior: nx = bx+vx queda dentro, asi la rama horizontal no toca vy
            state = (BOARD_W, BOARD_H, 4, by, 1, vy, 0, 0, 0, 0, 0)
            out = ref.step(state, 0, 0)
            observado = 1 if out[5] != vy else 0
            esperado = int(table[op])
            if observado != esperado:
                fallos += 1
                print(f"FAIL 0x{op:02x} by={by} vy={vy:+d}: oraculo {observado} != tabla {esperado}",
                      file=sys.stderr)
        print(f"check bounce: {len(table)} puntos del dominio vs oraculo -> "
              f"{'PASS' if fallos == 0 else str(fallos) + ' FALLOS'}")
    else:
        for op in sorted(table):
            pl, by = decode_contact(op)
            # fila inicial elegida para que el eje vertical (sin rebote) deje la pelota en
            # `by`: by_start = by - vy, con vy=+1 salvo en by=0 donde toca vy=-1.
            vy = -1 if by == 0 else 1
            by_start = by - vy
            # via 1: lectura interior, la rama de gol no pisa `by`, asi el oraculo nos da la
            # fila post-vertical real (en la via 2 un Gol la reemplaza por h//2).
            interior = ref.step((BOARD_W, BOARD_H, 4, by_start, 1, vy, pl, 0, 0, 0, 0), 0, 0)
            if interior[3] != by or interior[6] != pl:
                fallos += 1
                print(f"FAIL 0x{op:02x} precondiciones: by_after={interior[3]} != {by} o "
                      f"pl_after={interior[6]} != {pl}", file=sys.stderr)
                continue
            # via 2: la misma fila post-vertical, ahora contra la pared izquierda.
            out = ref.step((BOARD_W, BOARD_H, 0, by_start, -1, vy, pl, 0, 0, 0, 0), 0, 0)
            golpe = 1 if (out[2] == 0 and out[4] == 1) else 0
            esperado = int(table[op])
            if golpe != esperado:
                fallos += 1
                print(f"FAIL 0x{op:02x} pl={pl} by={by}: oraculo {golpe} != tabla {esperado}",
                      file=sys.stderr)
        print(f"check contact: {len(table)} puntos del dominio vs oraculo -> "
              f"{'PASS' if fallos == 0 else str(fallos) + ' FALLOS'}")
    return 0 if fallos == 0 else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("mode", choices=["encode", "expect", "emit", "check"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--kind", default="bounce", choices=list(KINDS))
    a = ap.parse_args(argv[1:])

    try:
        if a.mode == "encode":
            if len(a.args) != 2:
                raise ValueError("encode espera <by> <vy>")
            by, vy = int(a.args[0]), int(a.args[1])
            sys.stdout.write(f"{encode_bounce(by, vy):02x}\n")
            return 0
        if a.mode == "expect":
            if len(a.args) != 1:
                raise ValueError("expect espera <opcode_hex>")
            op = int(a.args[0], 16)
            table = marker_table(a.kind)
            if op not in table:
                raise ValueError(f"opcode sin ruta: 0x{op:02x}")
            sys.stdout.write(f"{table[op]}\n")
            return 0
        if a.mode == "emit":
            text = header_block(a.kind) + emit_hell(a.kind)
            if a.out:
                Path(a.out).write_text(text, encoding="utf-8", newline="\n")
                print(f"escribio {a.out} (kind={a.kind}, {len(domain(a.kind))} rutas, "
                      f"{len(text.encode())} bytes)")
            else:
                sys.stdout.write(text)
            return 0
        if a.mode == "check":
            return check(a.kind)
    except (ValueError, IndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
