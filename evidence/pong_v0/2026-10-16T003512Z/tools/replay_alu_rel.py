#!/usr/bin/env python3
"""replay_alu_rel.py — control de que MI harness coincide con la evidencia sellada de ALU_REL.

Por que existe este script
--------------------------
`audit_alu_rel_isa.py` midio que el kernel `alu_rel_pass25.mb` se equivoca fuera del corpus
sellado (`CMP_EQ` falla en la diagonal `a == a` para a en {0,1,3}). Antes de afirmar eso como
negativo hace falta descartar la explicacion alternativa: que sea YO quien lee mal la ISA.

Este script no inventa nada: transcribe LOS 25 VECTORES TAL CUAL aparecen en
`MALBOLGE-MB-DATABASE/vm_malbolge/ALU_REL_STATUS.md`, con su salida esperada Y sus pasos
documentados por vector (Oracle y Runner C), y los vuelve a ejecutar aqui contra la copia
verbatim del kernel sellado en los TRES interpretes Clasicos.

Control doble por vector:
  1. salida == salida documentada,
  2. pasos A == pasos B == pasos C == pasos documentados.

Si los 25 pasan, mi lectura de la ISA es exacta y el negativo de la auditoria es propiedad del
kernel, no del harness. Si alguno falla, el problema es mio y el negativo NO se afirma.

Reglas que cumple
-----------------
- Upstream abierto SOLO en lectura; el kernel se usa por su SHA-256 sellado.
- Anexo A.1: hex crudo y recorte de framing registrados por interprete.
- Anexo A.2: el veredicto apoya en `status` de stderr y en la salida, nunca en `$?`.
- Salida LF exclusivo, sin CR, sin BOM.

Uso:
    replay_alu_rel.py vector --index 15       > hex del stream de ese vector
    replay_alu_rel.py run [--max-steps 300000] [-o informe.json]
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
REPO = HERE.parents[2]
DB = REPO.parent / "MALBOLGE-MB-DATABASE"
ENGINE_A = REPO.parent / "Malbolge-Engine" / "malbolge"
ENGINE_B = DB / "runners" / "malbolge-original" / "malbolge"
ORACLE_C_SRC = DB / "tools" / "oracle_classic.py"
KERNEL = HERE.parent / "mbir_alu_rel_pass25.mb"
KERNEL_SHA = "3b6c011bf3f8f1c7bb610b99812956d7268719557b81ec7e85d481edf240f977"
LIMITE_CLASICO = 3 ** 10

_STEPS = re.compile(r"steps:\s*(\d+)\s*\|\s*status:\s*([A-Z_]+)")

# Los 25 vectores de ALU_REL_STATUS.md, en el mismo orden que la tabla de evidencia.
# (stream_hex, significado, salida esperada en hex, pasos documentados)
VECTORES = [
    ("01 41 10 00", "Baseline 1: PUSH 'A', OUT, HALT", "41", 63_937),
    ("01 41 01 42 10 10 00", "Baseline 2: PUSH 'A', PUSH 'B', OUT, OUT, HALT", "4241", 69_179),
    ("00", "Baseline 3: HALT inmediato", "", 58_689),
    ("01 02 01 03 02 10 00", "ADD 2 + 3 = 5", "05", 73_681),
    ("01 04 01 03 02 10 00", "ADD 4 + 3 = 7", "07", 72_471),
    ("01 01 01 01 02 10 00", "ADD 1 + 1 = 2", "02", 71_976),
    ("01 02 01 00 02 10 00", "ADD 2 + 0 = 2", "02", 71_535),
    ("01 04 01 02 03 10 00", "SUB 4 - 2 = 2", "02", 72_885),
    ("01 02 01 02 03 10 00", "SUB 2 - 2 = 0", "00", 74_098),
    ("01 02 01 01 03 10 00", "SUB 2 - 1 = 1", "01", 72_553),
    ("01 02 01 00 03 10 00", "SUB 2 - 0 = 2", "02", 72_107),
    ("01 01 01 01 02 01 01 03 10 00", "Chained Arith 1: (1+1)-1 = 1", "01", 80_592),
    ("01 01 01 01 02 01 02 03 10 00", "Chained Arith 2: (1+1)-2 = 0", "00", 82_137),
    ("01 02 01 01 03 01 01 02 10 00", "Chained Arith 3: (2-1)+1 = 2", "02", 80_592),
    ("01 02 01 02 04 10 00", "CMP_EQ 2 == 2 (true)", "01", 74_530),
    ("01 02 01 01 04 10 00", "CMP_EQ 2 == 1 (false)", "00", 72_991),
    ("01 02 01 00 04 10 00", "CMP_EQ 2 == 0 (false)", "00", 72_545),
    ("01 04 01 02 04 10 00", "CMP_EQ 4 == 2 (false)", "00", 73_323),
    ("01 01 01 01 02 01 02 04 10 00", "Chained Rel 1: (1+1)==2 -> 1", "01", 82_569),
    ("01 01 01 01 02 01 01 04 10 00", "Chained Rel 2: (1+1)==1 -> 0", "00", 81_030),
    ("01 04 01 02 03 01 02 04 10 00", "Chained Rel 3: (4-2)==2 -> 1", "01", 83_478),
    ("01 04 01 02 03 01 01 04 10 00", "Chained Rel 4: (4-2)==1 -> 0", "00", 81_939),
    ("01 04 01 02 03 01 00 04 10 00", "Chained Rel 5: (4-2)==0 -> 0", "00", 81_493),
    ("01 02 01 00 02 01 02 04 10 00", "Chained Rel 6: (2+0)==2 -> 1", "01", 82_128),
    ("01 02 01 00 02 01 01 04 10 00", "Chained Rel 7: (2+0)==1 -> 0", "00", 80_589),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_kernel() -> None:
    if not KERNEL.is_file():
        raise SystemExit(f"no existe la copia del kernel: {KERNEL}")
    real = sha256(KERNEL)
    if real != KERNEL_SHA:
        raise SystemExit(f"kernel copiado no coincide con el sellado: {real}")


def stream_de(idx: int) -> bytes:
    return bytes(int(t, 16) for t in VECTORES[idx][0].split())


def describe(st: bytes) -> str:
    return " ".join(f"{x:02x}" for x in st)


def load_oracle_module():
    spec = importlib.util.spec_from_file_location("oracle_classic_upstream", ORACLE_C_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def deframe(raw: bytes) -> bytes:
    if raw.endswith(b"\r\n"):
        return raw[:-2]
    if raw.endswith(b"\n"):
        return raw[:-1]
    return raw


def run_native(exe: Path, st: bytes, max_steps: int) -> dict:
    p = subprocess.run([str(exe), str(KERNEL), str(max_steps)], input=st,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    m = _STEPS.search(p.stderr.decode("utf-8", "replace"))
    return {"stdout_raw_hex": p.stdout.hex(), "salida_hex": deframe(p.stdout).hex(),
            "pasos": int(m.group(1)) if m else None, "status": m.group(2) if m else None,
            "rc": p.returncode}


def run_model(mod, src_text: str, st: bytes, max_steps: int) -> dict:
    text, steps, status = mod.run(src_text, max_steps, st.decode("latin-1"))
    raw = text.encode("latin-1")
    return {"stdout_raw_hex": raw.hex(), "salida_hex": deframe(raw).hex(),
            "pasos": steps, "status": status, "rc": 0}


def one_case(mod, src_text: str, idx: int, max_steps: int) -> dict:
    st = stream_de(idx)
    stream_hex, significado, esperado_hex, pasos_doc = VECTORES[idx]
    a = run_native(ENGINE_A, st, max_steps)
    b = run_native(ENGINE_B, st, max_steps)
    c = run_model(mod, src_text, st, max_steps)
    intps = (a, b, c)
    salidas = tuple(x["salida_hex"] for x in intps)
    pasos = tuple(x["pasos"] for x in intps)
    if any(x["status"] != "HALTED" for x in intps):
        veredicto = "NO_HALTO"
    elif len(set(salidas)) != 1 or len(set(pasos)) != 1:
        veredicto = "DESACUERDO_ENTRE_INTERPRETES"
    elif salidas[0] != esperado_hex:
        veredicto = "SALIDA_DISTINTA_A_EVIDENCIA_SELLADA"
    elif any(p != pasos_doc for p in pasos):
        veredicto = "PASOS_DISTINTOS_A_EVIDENCIA_SELLADA"
    else:
        veredicto = "FIEL_A_EVIDENCIA_SELLADA"
    assert describe(st) == stream_hex, f"transcripcion del vector {idx + 1} no es literal"
    return {"indice": idx + 1, "significado": significado, "stream_hex": stream_hex,
            "esperado_hex": esperado_hex or "(vacio)", "pasos_documentados": pasos_doc,
            "salida_observada_hex": salidas[0] or "(vacio)", "pasos": list(pasos),
            "salida_fiel": salidas == (esperado_hex,) * 3,
            "pasos_fieles": pasos == (pasos_doc,) * 3,
            "tres_vias_iguales": len(set(salidas)) == 1 and len(set(pasos)) == 1,
            "veredicto": veredicto, "A": a, "B": b, "C": c}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["vector", "run"])
    ap.add_argument("--index", type=int)
    ap.add_argument("--max-steps", type=int, default=300_000)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv[1:])
    check_kernel()

    if a.mode == "vector":
        if a.index is None or not 1 <= a.index <= len(VECTORES):
            print("error: vector espera --index 1..25", file=sys.stderr)
            return 2
        sys.stdout.write(stream_de(a.index - 1).hex(" ") + "\n")
        return 0
    if a.mode == "run":
        for exe in (ENGINE_A, ENGINE_B):
            if not exe.is_file():
                raise SystemExit(f"no existe el interprete: {exe}")
        mod = load_oracle_module()
        if mod.MEM_SIZE != LIMITE_CLASICO:
            raise SystemExit(f"el modelo C no es Clasico 3^10: MEM_SIZE={mod.MEM_SIZE}")
        src_text = KERNEL.read_text(encoding="ascii")
        planos = [one_case(mod, src_text, i, a.max_steps) for i in range(len(VECTORES))]
        n_fiel = sum(1 for x in planos if x["veredicto"] == "FIEL_A_EVIDENCIA_SELLADA")
        informe = {
            "objetivo": "control de que el harness de MALGAMES reproduce los 25 vectores "
                        "sellados de ALU_REL_STATUS.md en salida Y en pasos",
            "fuente_de_los_vectores": "MALBOLGE-MB-DATABASE/vm_malbolge/ALU_REL_STATUS.md "
                                      "(transcripcion literal, sin retonques)",
            "kernel": {"archivo": str(KERNEL), "sha256": sha256(KERNEL),
                       "bytes": KERNEL.stat().st_size,
                       "margen_celdas": LIMITE_CLASICO - KERNEL.stat().st_size},
            "interpretes": {"A": str(ENGINE_A), "B": str(ENGINE_B), "C": str(ORACLE_C_SRC)},
            "max_steps": a.max_steps,
            "vectores": len(VECTORES),
            "fieles": n_fiel,
            "todo_fiel": n_fiel == len(VECTORES),
            "casos": planos,
        }
        texto = json.dumps(informe, indent=2, ensure_ascii=False) + "\n"
        if a.out:
            Path(a.out).write_text(texto, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(texto)
        return 0 if informe["todo_fiel"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
