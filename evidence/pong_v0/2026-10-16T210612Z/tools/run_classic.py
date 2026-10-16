#!/usr/bin/env python3
"""run_classic.py — ejecuta un predicado Pong dentro de la VM Malbolge CLASICA (3^10).

Corre cada punto del dominio como UN byte en stdin del artefacto `.mb`, en TRES
interpretes Clasicos independientes, y contrasta lo que imprime la VM contra la tabla
derivada por `pong_codegen.py` y contra el oraculo `oracle/pong_reference.py`. El host no
calcula el predicado en ningun momento: escribe un byte, lee el byte que imprime la VM, y
compara.

    A = `Malbolge-Engine/malbolge`                  (ELF nativo)
    B = `MALBOLGE-MB-DATABASE/runners/malbolge-original/malbolge`  (ELF nativo, otro codigo)
    C = `MALBOLGE-MB-DATABASE/tools/oracle_classic.py` (modelo Python de referencia; su CLI
        no admite stdin, asi que se llama a run() del modulo con el stdin inyectado)

Los tres implementan el Clásico de 3^10 celdas; ninguno es el Unshackled de 6 ternas.

Uso:
    python3 run_classic.py --kind bounce  [--max-steps 2000000] [-o informe.json]
    python3 run_classic.py --kind contact [--max-steps 2000000] [-o informe.json]

Salida: JSON puro en stdout (o en -o). Veredicto por caso: PASS / DESCUADRE / SIN_SALIDA /
NO_HALTO / MAX_PASOS. Exit 0 exige TODOS los casos PASS y A==B==C en salida y en pasos.
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
REPO = HERE.parents[2]                                  # MALGAMES/
DB = REPO.parent / "MALBOLGE-MB-DATABASE"
ENGINE_A = REPO.parent / "Malbolge-Engine" / "malbolge"
ENGINE_B = DB / "runners" / "malbolge-original" / "malbolge"
ORACLE_C_SRC = DB / "tools" / "oracle_classic.py"

sys.path.insert(0, str(HERE.parent))
import pong_codegen as cg                               # noqa: E402

_STEPS = re.compile(r"steps:\s*(\d+)\s*\|\s*status:\s*([A-Z_]+)")
MEM_SIZE = 3 ** 10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_oracle_module():
    spec = importlib.util.spec_from_file_location("oracle_classic_upstream", ORACLE_C_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def deframe(raw: bytes) -> bytes:
    """Quita UN unico salto de linea final: framing del runner, no salida del programa.

    Medido, no asumido: los dos ELF escriben el byte del programa seguido de 0x0A en stdout
    y dejan `steps: N | status: S` en stderr. El mismo recorte hace
    `MALBOLGE-MB-DATABASE/vm_malbolge/tests/buildrun.py:run_runner()` (lineas 66-70) para
    su runner.
    """
    if raw.endswith(b"\r\n"):
        return raw[:-2]
    if raw.endswith(b"\n"):
        return raw[:-1]
    return raw


def run_native(exe: Path, prog: Path, one_byte: bytes, max_steps: int) -> dict:
    p = subprocess.run([str(exe), str(prog), str(max_steps)], input=one_byte,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    m = _STEPS.search(p.stderr.decode("utf-8", "replace"))
    out = deframe(p.stdout)
    return {
        "stdout_raw_hex": p.stdout.hex(),
        "salida": out.decode("latin-1"),
        "pasos": int(m.group(1)) if m else None,
        "status": m.group(2) if m else None,
        "rc": p.returncode,
        "stderr": p.stderr.decode("utf-8", "replace").strip(),
    }


def run_model(mod, src_text: str, one_byte: bytes, max_steps: int) -> dict:
    text, steps, status = mod.run(src_text, max_steps, one_byte.decode("latin-1"))
    out = text.encode("latin-1")
    return {
        "stdout_raw_hex": out.hex(),
        "salida": out.decode("latin-1"),
        "pasos": steps,
        "status": status,
        "rc": 0,
    }


def one_case(kind: str, mod, src_text: str, prog: Path, op: int, expect: str,
             max_steps: int) -> dict:
    one_byte = bytes([op])
    a = run_native(ENGINE_A, prog, one_byte, max_steps)
    b = run_native(ENGINE_B, prog, one_byte, max_steps)
    c = run_model(mod, src_text, one_byte, max_steps)
    interpretes = (a, b, c)
    salidas = tuple(x["salida"] for x in interpretes)
    pasos = tuple(x["pasos"] for x in interpretes)
    conocido = {
        "bounce": lambda o: f"by={cg.decode_bounce(o)[0]}, vy={cg.decode_bounce(o)[1]:+d}",
        "contact": lambda o: f"pl={cg.decode_contact(o)[0]}, by={cg.decode_contact(o)[1]}",
    }[kind](op)
    if any(s == "" for s in salidas):
        veredicto = "SIN_SALIDA"
    elif any(x["status"] != "HALTED" for x in interpretes):
        veredicto = "NO_HALTO"
    elif any(s is not None and s >= max_steps for s in pasos):
        veredicto = "MAX_PASOS"
    elif any(s != expect for s in salidas) or len(set(pasos)) != 1:
        veredicto = "DESCUADRE"
    else:
        veredicto = "PASS"
    return {
        "opcode": f"{op:02x}",
        "decodificado": conocido,
        "esperado_host": expect,
        "A": a,
        "B": b,
        "C": c,
        "tres_vias_iguales": len(set(salidas)) == 1 and len(set(pasos)) == 1,
        "veredicto": veredicto,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(cg.KINDS))
    ap.add_argument("--max-steps", type=int, default=2_000_000)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv[1:])

    prog = HERE.parent / f"pong_{a.kind}_v0.mb"
    if not prog.is_file():
        sys.exit(f"no existe el artefacto: {prog}")
    for exe in (ENGINE_A, ENGINE_B):
        if not exe.is_file():
            sys.exit(f"no existe el interprete: {exe}")
    mod = load_oracle_module()
    src_text = prog.read_text(encoding="ascii")
    if mod.MEM_SIZE != MEM_SIZE:
        sys.exit(f"el modelo C no es Clásico 3^10: MEM_SIZE={mod.MEM_SIZE}")

    domain = cg.domain(a.kind)
    table = cg.marker_table(a.kind)
    casos = [one_case(a.kind, mod, src_text, prog, op, table[op], a.max_steps)
           for op, _ in domain]
    n_ok = sum(1 for x in casos if x["veredicto"] == "PASS")
    n_igual = sum(1 for x in casos if x["tres_vias_iguales"])
    informe = {
        "predicado": a.kind,
        "tablero": f"{cg.BOARD_W}x{cg.BOARD_H}",
        "artefacto": str(prog),
        "artefacto_sha256": sha256(prog),
        "artefacto_bytes": prog.stat().st_size,
        "celdas_clasico": MEM_SIZE,
        "margen_celdas": MEM_SIZE - prog.stat().st_size,
        "interpretes": {"A": str(ENGINE_A), "B": str(ENGINE_B), "C": str(ORACLE_C_SRC)},
        "max_steps": a.max_steps,
        "dominio_puntos": len(domain),
        "pass": n_ok,
        "tres_vias_iguales": n_igual,
        "casos": casos,
        "todo_pass": n_ok == len(domain) and n_igual == len(domain),
    }
    texto = json.dumps(informe, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).write_text(texto, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(texto)
    return 0 if informe["todo_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
