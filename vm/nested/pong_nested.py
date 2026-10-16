#!/usr/bin/env python3
"""pong_nested.py — ruta NESTED_VM de MALGAMES/PONG_V0: la VM deriva la fila post-vertical
y evalúa la puerta de gol sobre DATOS, dentro de Malbolge Clásico.

Qué se intenta aquí (y en qué se diferencia de `vm/classic/`)
-------------------------------------------------------------
`vm/classic/` demuestra dos predicados sobre un dominio finito, pero cada ruta imprime una
constante horneada en tiempo de codegen y el número de rutas crece con el producto del dominio
(medido: ~1 170 B por ruta; 32 rutas NO ensamblan). Eso no encadena nada: `contact` recibe la
fila post-vertical ya codificada por el host.

Aquí no se escribe HeLL nuevo. Se usa el kernel MBIR **ya sellado** `alu_rel_pass25.mb`
(SHA-256 3b6c011b…, 57 511 B,Demonstrated 25/25), que es una máquina de pila LIFO de 2 ranuras
con fetch loop y `ADD 0x02` / `SUB 0x03` / `CMP_EQ 0x04` / `PUSH_CONST 0x01` / `OUT_BYTE 0x10`
/ `HALT 0x00`. Su propio manifiesto documenta cadenas `(1 + 1) == 2 -> 1`, que es exactamente la
forma algebraica de la puerta de Pong.

La puerta se expresa como un flujo de bytecodes **cuya forma no depende de la entrada**:

    01 <by>  01 01  03      s0 = by - 1
    01 <e>   02            s0 = by - 1 + e
    01 <e>   02            s0 = by - 1 + 2e          <-- esto es ny
    01 <pl>  04            s0 = (ny == pl)
    10 00                  OUT, HALT

con `e` ∈ {0,1} la codificación de `vy` ∈ {-1,+1}. La identidad a comprobar es
`by - 1 + 2e == by + vy`, que vale para todo `by` interior (0 < by < h-1) y ambos signos de `vy`.
En los bordes (`by=0, vy=-1` y `by=h-1, vy=+1`) el rebote invierte el signo y hace falta
bifurcacion condicional; ese caso está **fuera de alcance** y se declara (§A.5 del contrato:
este intento reduce ALCANCE, no encoding).

Qué NO afirma este script: un tick completo, lectura del framing `pong1`, render de frames, ni
`DIRECT_VM`. Aquí el programa Malbolge es una segunda VM (MBIR) y el pong vive en su stream de
datos; la separación runner/motor se evidencia con los pasos que dependen de los VALORES.

Uso:
    pong_nested.py stream --kind ny   --by 1 --e 0              > hex del stream
    pong_nested.py stream --kind gate --by 1 --e 0 --pl 2       > hex del stream
    pong_nested.py expect --kind gate --by 1 --e 0 --pl 2       > 0|1 derivado del oraculo
    pong_nested.py run [--max-steps 500000] [-o informe.json]

Salida: LF exclusivo, sin CR, sin BOM. Entrada invalida: stderr + exit != 0 + cero bytes en stdout.
Upstream se abre SOLO en lectura; este script no escribe fuera de MALGAMES.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
HERE_DIR = HERE.parent                              # MALGAMES/vm/nested/
REPO = HERE.parents[2]                              # MALGAMES/
DB = REPO.parent / "MALBOLGE-MB-DATABASE"
ENGINE_A = REPO.parent / "Malbolge-Engine" / "malbolge"
ENGINE_B = DB / "runners" / "malbolge-original" / "malbolge"
ORACLE_C_SRC = DB / "tools" / "oracle_classic.py"
KERNEL = HERE_DIR / "mbir_alu_rel_pass25.mb"

# SHA-256 documentados en vm_malbolge/ALU_REL_STATUS.md; si el copiado no coincide, abortamos.
KERNEL_SHA_ESPERADO = "3b6c011bf3f8f1c7bb610b99812956d7268719557b81ec7e85d481edf240f977"
KERNEL_BYTES = 57511
LIMITE_CLASICO = 3 ** 10

sys.path.insert(0, str(REPO / "vm" / "classic"))
import pong_codegen as cg                              # noqa: E402  (dominio y tablas selladas)

# ------------------------------------------------------------------ ISA del kernel MBIR ---
HALT, PUSH, ADD, SUB, CMPEQ, OUT = 0x00, 0x01, 0x02, 0x03, 0x04, 0x10

BOARD_W, BOARD_H = cg.BOARD_W, cg.BOARD_H             # 8x4, congelado por el contrato
BY_INTERIOR = tuple(range(1, BOARD_H - 1))            # by en 1..h-2: sin reflexion vertical
E_VALORES = (0, 1)                                    # e=0 -> vy=-1 ; e=1 -> vy=+1
PL_VALORES = tuple(range(BOARD_H))                    # pl en 0..h-1

_STEPS = re.compile(r"steps:\s*(\d+)\s*\|\s*status:\s*([A-Z_]+)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vy_de_e(e: int) -> int:
    if e not in E_VALORES:
        raise ValueError(f"e fuera de {E_VALORES}: {e}")
    return -1 if e == 0 else 1


def check_kernel() -> None:
    if not KERNEL.is_file():
        raise SystemExit(f"no existe la copia del kernel: {KERNEL}")
    real = sha256(KERNEL)
    if real != KERNEL_SHA_ESPERADO:
        raise SystemExit(f"kernel copiado no coincide con el sellado: {real} != {KERNEL_SHA_ESPERADO}")
    if KERNEL.stat().st_size != KERNEL_BYTES:
        raise SystemExit(f"kernel con tamano inesperado: {KERNEL.stat().st_size}")


def load_oracle_module():
    spec = importlib.util.spec_from_file_location("oracle_classic_upstream", ORACLE_C_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------- streams (bytecode) ---
def stream_ny(by: int, e: int) -> bytes:
    """La VM calcula la fila post-vertical y la imprime cruda: prueba de derivacion."""
    return bytes([PUSH, by, PUSH, 1, SUB, PUSH, e, ADD, PUSH, e, ADD, OUT, HALT])


def stream_gate(by: int, e: int, pl: int) -> bytes:
    """La VM calcula ny, lo compara con pl y imprime el booleano: la cadena completa."""
    return bytes([PUSH, by, PUSH, 1, SUB, PUSH, e, ADD, PUSH, e, ADD,
                  PUSH, pl, CMPEQ, OUT, HALT])


def build_stream(kind: str, by: int, e: int, pl: int | None = None) -> bytes:
    if not 0 <= by <= BOARD_H - 1:
        raise ValueError(f"by fuera de 0..{BOARD_H - 1}: {by}")
    if by not in BY_INTERIOR:
        raise ValueError(f"by={by} esta en borde: la reflexion exige bifurcacion y no es "
                         f"expresable en este kernel (dominio declarado: by en {BY_INTERIOR})")
    vy_de_e(e)
    if kind == "ny":
        return stream_ny(by, e)
    if kind == "gate":
        if pl is None:
            raise ValueError("kind=gate espera --pl")
        if not 0 <= pl <= BOARD_H - 1:
            raise ValueError(f"pl fuera de 0..{BOARD_H - 1}: {pl}")
        return stream_gate(by, e, pl)
    raise ValueError(f"kind desconocido: {kind}")


def describe(stream: bytes) -> str:
    return " ".join(f"{b:02x}" for b in stream)


# --------------------------------------------------------------- expectativas (oraculo) ---
def oracle_ny(by: int, e: int) -> int:
    """Fila post-vertical segun `oracle/pong_reference.py`, sin reimplementar la transicin."""
    ref = _ref_mod()
    out = ref.step((BOARD_W, BOARD_H, 4, by, 1, vy_de_e(e), 0, 0, 0, 0, 0), 0, 0)
    return out[3]


def oracle_gate(by: int, e: int, pl: int) -> int:
    """Gol convertido en golpe de paleta segun el oraculo: pelota en la pared, vx=-1."""
    ref = _ref_mod()
    out = ref.step((BOARD_W, BOARD_H, 0, by, -1, vy_de_e(e), pl, 0, 0, 0, 0), 0, 0)
    return 1 if (out[2] == 0 and out[4] == 1) else 0


_REF = None


def _ref_mod():
    global _REF
    if _REF is None:
        sys.path.insert(0, str(REPO / "oracle"))
        import pong_reference                                  # noqa: E402
        _REF = pong_reference
    return _REF


# ------------------------------------------------------------------------- ejecucion ---
def deframe(raw: bytes) -> bytes:
    """Quita UN unico 0x0A final: framing del runner, no salida del programa (Anexo A.1).

    Los dos ELF appendan un salto de linea; se recorta SIEMPRE el ultimo byte y solo si es
    0x0A, y el hex crudo queda registrado intacto en el informe. Ningun byte esperado por este
    experimento vale 0x0A, as que el recorte no puede comerse un dato del programa.
    """
    if raw.endswith(b"\r\n"):
        return raw[:-2]
    if raw.endswith(b"\n"):
        return raw[:-1]
    return raw


def run_native(exe: Path, stream: bytes, max_steps: int) -> dict:
    p = subprocess.run([str(exe), str(KERNEL), str(max_steps)], input=stream,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    m = _STEPS.search(p.stderr.decode("utf-8", "replace"))
    return {
        "stdout_raw_hex": p.stdout.hex(),
        "salida_hex": deframe(p.stdout).hex(),
        "pasos": int(m.group(1)) if m else None,
        "status": m.group(2) if m else None,
        "rc": p.returncode,
    }


def run_model(mod, src_text: str, stream: bytes, max_steps: int) -> dict:
    text, steps, status = mod.run(src_text, max_steps, stream.decode("latin-1"))
    raw = text.encode("latin-1")
    return {
        "stdout_raw_hex": raw.hex(),
        "salida_hex": deframe(raw).hex(),
        "pasos": steps,
        "status": status,
        "rc": 0,
    }


def one_case(mod, src_text: str, case: dict, max_steps: int) -> dict:
    stream = case["stream"]
    a = run_native(ENGINE_A, stream, max_steps)
    b = run_native(ENGINE_B, stream, max_steps)
    c = run_model(mod, src_text, stream, max_steps)
    intps = (a, b, c)
    salidas = tuple(x["salida_hex"] for x in intps)
    pasos = tuple(x["pasos"] for x in intps)
    esperado = f"{case['esperado']:02x}"
    if any(s == "" for s in salidas):
        veredicto = "SIN_SALIDA"
    elif any(x["status"] != "HALTED" for x in intps):
        veredicto = "NO_HALTO"
    elif any(s is not None and s >= max_steps for s in pasos):
        veredicto = "MAX_PASOS"
    elif any(s != esperado for s in salidas) or len(set(pasos)) != 1:
        veredicto = "DESCUADRE"
    else:
        veredicto = "PASS"
    return {**{k: v for k, v in case.items() if k != "stream"},
            "stream_hex": describe(stream),
            "longitud_stream_bytes": len(stream),
            "A": a, "B": b, "C": c,
            "tres_vias_iguales": len(set(salidas)) == 1 and len(set(pasos)) == 1,
            "veredicto": veredicto}


# ----------------------------------------------------------------------------- dominio ---
def casos_controles() -> list[dict]:
    """Reproduce tres vectores documentados del kernel: si fallan, el motor no est vivo aqui."""
    return [
        {"id": "control_add_2_3", "kind": "control", "nota": "ADD 2+3=5 (vector 4 de ALU_REL)",
         "stream": bytes([PUSH, 2, PUSH, 3, ADD, OUT, HALT]), "esperado": 0x05},
        {"id": "control_chain_true", "kind": "control",
         "nota": "(1+1)==2 -> 1 (vector 19 de ALU_REL: la forma algebraica que imitamos)",
         "stream": bytes([PUSH, 1, PUSH, 1, ADD, PUSH, 2, CMPEQ, OUT, HALT]), "esperado": 0x01},
        {"id": "control_chain_false", "kind": "control",
         "nota": "(2+0)==1 -> 0 (vector 22 de ALU_REL)",
         "stream": bytes([PUSH, 2, PUSH, 0, ADD, PUSH, 1, CMPEQ, OUT, HALT]), "esperado": 0x00},
    ]


def casos_derivacion() -> list[dict]:
    out = []
    for by in BY_INTERIOR:
        for e in E_VALORES:
            ny = oracle_ny(by, e)
            out.append({"id": f"ny_by{by}_e{e}", "kind": "ny",
                        "nota": f"by={by}, vy={vy_de_e(e):+d} -> fila post-vertical derivada",
                        "by": by, "e": e, "stream": build_stream("ny", by, e),
                        "esperado": ny})
    return out


def casos_cadena() -> list[dict]:
    out = []
    for by in BY_INTERIOR:
        for e in E_VALORES:
            ny = oracle_ny(by, e)
            for pl in PL_VALORES:
                bit = oracle_gate(by, e, pl)
                # condicion (a) del acuerdo: la tabla `contact` ya sellada tiene que decir lo mismo
                sellado = int(cg.marker_table("contact")[cg.encode_contact(pl, ny)])
                out.append({"id": f"gate_by{by}_e{e}_pl{pl}", "kind": "gate",
                            "by": by, "e": e, "pl": pl, "ny_oraculo": ny,
                            "nota": f"ny derivado={ny}; puerta oraculo={bit}; puerta tabla sellada={sellado}",
                            "esperado": bit, "coincide_con_sello": bit == sellado,
                            "stream": build_stream("gate", by, e, pl)})
    return out


# ------------------------------------------------------------------------------------ main ---
def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["stream", "expect", "run"])
    ap.add_argument("--kind", default="gate", choices=["ny", "gate"])
    ap.add_argument("--by", type=int)
    ap.add_argument("--e", type=int)
    ap.add_argument("--pl", type=int, default=None)
    ap.add_argument("--max-steps", type=int, default=500_000)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv[1:])

    check_kernel()

    try:
        if a.mode == "stream":
            if a.by is None or a.e is None:
                raise ValueError("stream espera --by y --e" + (" y --pl" if a.kind == "gate" else ""))
            sys.stdout.write(describe(build_stream(a.kind, a.by, a.e, a.pl)) + "\n")
            return 0
        if a.mode == "expect":
            if a.by is None or a.e is None:
                raise ValueError("expect espera --by y --e")
            if a.kind == "ny":
                sys.stdout.write(f"{oracle_ny(a.by, a.e)}\n")
                return 0
            if a.pl is None:
                raise ValueError("expect kind=gate espera --pl")
            sys.stdout.write(f"{oracle_gate(a.by, a.e, a.pl)}\n")
            return 0
        if a.mode == "run":
            for exe in (ENGINE_A, ENGINE_B):
                if not exe.is_file():
                    raise SystemExit(f"no existe el interprete: {exe}")
            mod = load_oracle_module()
            if mod.MEM_SIZE != LIMITE_CLASICO:
                raise SystemExit(f"el modelo C no es Clasico 3^10: MEM_SIZE={mod.MEM_SIZE}")
            src_text = KERNEL.read_text(encoding="ascii")

            grupos = {"controles": casos_controles(),
                      "derivacion_ny": casos_derivacion(),
                      "cadena_gate": casos_cadena()}
            resultados = {g: [one_case(mod, src_text, c, a.max_steps) for c in cs]
                          for g, cs in grupos.items()}
            planos = [x for v in resultados.values() for x in v]
            n_ok = sum(1 for x in planos if x["veredicto"] == "PASS")
            n_igual = sum(1 for x in planos if x["tres_vias_iguales"])
            gates = resultados["cadena_gate"]
            n_sello = sum(1 for x in gates if x["coincide_con_sello"])
            informe = {
                "ruta": "NESTED_VM (MBIR sobre Malbolge Clasico)",
                "kernel": {"archivo": str(KERNEL), "sha256": sha256(KERNEL),
                           "bytes": KERNEL.stat().st_size,
                           "margen_celdas": LIMITE_CLASICO - KERNEL.stat().st_size,
                           "origen": "copia verbatim de "
                                     "MALBOLGE-MB-DATABASE/vm_malbolge/evidence/artifacts/"
                                     "alu_rel_pass25.mb",
                           "estado_upstream": "solo lectura; SHA-256 verificado antes de correr"},
                "dominio_declarado": {
                    "by": list(BY_INTERIOR), "e": list(E_VALORES), "pl": list(PL_VALORES),
                    "motivo": "en borde (by=0,vy=-1 y by=h-1,vy=+1) la reflexion invierte el "
                              "signo y exige bifurcacion condicional, que este kernel no tiene; "
                              "se reduce ALCANCE, no encoding (Anexo A.5)",
                    "puntos_cadena": len(gates)},
                "interpretes": {"A": str(ENGINE_A), "B": str(ENGINE_B), "C": str(ORACLE_C_SRC)},
                "max_steps": a.max_steps,
                "controles": {"total": len(resultados["controles"]),
                              "pass": sum(1 for x in resultados["controles"]
                                          if x["veredicto"] == "PASS")},
                "derivacion_ny": {"total": len(resultados["derivacion_ny"]),
                                  "pass": sum(1 for x in resultados["derivacion_ny"]
                                              if x["veredicto"] == "PASS")},
                "cadena_gate": {"total": len(gates),
                                "pass": sum(1 for x in gates if x["veredicto"] == "PASS"),
                                "coincide_con_tabla_sellada": n_sello},
                "total_pass": n_ok, "total_puntos": len(planos),
                "tres_vias_iguales": n_igual,
                "todo_pass": n_ok == len(planos),
                "casos": resultados,
            }
            texto = json.dumps(informe, indent=2, ensure_ascii=False) + "\n"
            if a.out:
                Path(a.out).write_text(texto, encoding="utf-8", newline="\n")
            else:
                sys.stdout.write(texto)
            return 0 if informe["todo_pass"] else 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
