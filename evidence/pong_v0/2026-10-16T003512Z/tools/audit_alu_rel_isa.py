#!/usr/bin/env python3
"""audit_alu_rel_isa.py — auditoria de la ISA real del kernel MBIR `alu_rel_pass25.mb`.

Por que existe este script
--------------------------
`vm/nested/pong_nested.py` intento encadenar `bounce` -> `contact` expresando la puerta como
dataflow sobre el kernel Relational ALU ya sellado (MALBOLGE-MB-DATABASE/vm_malbolge/
ALU_REL_STATUS.md, 25/25, 57 511 B). Primer caso medido: `CMP_EQ 1 == 1` imprime `00`.
Eso no es un fallo de mi stream: es una propiedad del kernel que el corpus sellado no toca.

Observacion estructural que el corpus esconde: en los CUATRO vectores relacionales encadenados
de ALU_REL_STATUS.md el resultado de la aritmetica previa es siempre 2
((1+1)==2, (4-2)==2, (2+0)==2, y las variantes falsas comparan 2 contra 0/1/1). Es decir,
el dominio probado de `CMP_EQ` es `op1 == 2`, y la reflexividad `a == a` no esta probada para
ningun `a != 2`.

Que hace esta auditoria
----------------------
Recorre una rejilla explicita de operandos por cada opcode, con expectativa calculada por
aritmetica entera trivial (independiente de la VM), en TRES interpretes Clasicos
independientes, y devuelve la tabla exacta de que pares estan bien y que pares estan mal.
No reescribe ninguna expectativa para "hacer pasar" nada: un fallo aqui es un negativo
documentado contra el claim upstream, no contra MALGAMES.

Reglas que cumple
-----------------
- Upstream abierto SOLO en lectura; el kernel se usa por su SHA-256 sellado.
- Anexo A.1: se registra el hex crudo y el recorte de framing por interprete.
- Anexo A.2: el veredicto nunca apoya en `$?`; usa `status` de stderr y salida.
- Salida LF exclusivo, sin CR, sin BOM. Entrada invalida: stderr + exit != 0.

Uso:
    audit_alu_rel_isa.py grid            > lista de casos y expectativas (sin VM)
    audit_alu_rel_isa.py case --op SUB --a 2 --b 1   > hex del stream
    audit_alu_rel_isa.py run [--max-steps 300000] [-o informe.json]
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
MODULUS = 3 ** 10                                   # 59049: un resultado negativo envuelve aqui

HALT, PUSH, ADD, SUB, CMPEQ, OUT = 0x00, 0x01, 0x02, 0x03, 0x04, 0x10
_STEPS = re.compile(r"steps:\s*(\d+)\s*\|\s*status:\s*([A-Z_]+)")

# Rejilla: 0..4 cubre todo el dominio del tick `pong1` en tablero 8x4 (by, pl, ny en 0..3) y
# el maximo que el corpus sellado usa (4). AMBOS operandos hasta 4: la primera pasada uso
# op2 en 0..2 (lo que P1/P2 declaran clasificar) y eso dejo la diagonal `a == a` sin cubrir
# para a >= 3, contradiciendo la sonda ad hoc. Ahora la diagonal 0..4 queda medida entera.
OP1 = (0, 1, 2, 3, 4)
OP2 = (0, 1, 2, 3, 4)
OPS = ("ADD", "SUB", "CMPEQ")
NOMBRE = {"ADD": "ADD 0x02", "SUB": "SUB 0x03", "CMPEQ": "CMP_EQ 0x04"}
CODIGO = {"ADD": ADD, "SUB": SUB, "CMPEQ": CMPEQ}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_kernel() -> None:
    if not KERNEL.is_file():
        raise SystemExit(f"no existe la copia del kernel: {KERNEL}")
    real = sha256(KERNEL)
    if real != KERNEL_SHA:
        raise SystemExit(f"kernel copiado no coincide con el sellado: {real}")


def stream(op: str, a: int, b: int) -> bytes:
    return bytes([PUSH, a, PUSH, b, CODIGO[op], OUT, HALT])


def describe(st: bytes) -> str:
    return " ".join(f"{x:02x}" for x in st)


def expectativa(op: str, a: int, b: int):
    """Expectativa aritmetica trivial; el dominio que upstream deja de cubrir se marca aparte.

    Devuelve (esperado_o_None, en_dominio_declarado). None = el kernel no debe pronunciarse.
    """
    if op == "ADD":
        return a + b, True
    if op == "SUB":
        if a < b:
            return (a - b) % MODULUS, False          # upstream: "Arbitrary Signed" NO demostrado
        return a - b, True
    if op == "CMPEQ":
        return 1 if a == b else 0, True
    raise ValueError(op)


def casos() -> list[dict]:
    out = []
    for op in OPS:
        for a in OP1:
            for b in OP2:
                exp, en_dom = expectativa(op, a, b)
                out.append({"id": f"{op}_{a}_{b}", "op": op, "a": a, "b": b,
                            "stream": stream(op, a, b), "esperado": exp,
                            "en_dominio_declarado": en_dom})
    return out


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


def one_case(mod, src_text: str, c: dict, max_steps: int) -> dict:
    st = c["stream"]
    a = run_native(ENGINE_A, st, max_steps)
    b = run_native(ENGINE_B, st, max_steps)
    cc = run_model(mod, src_text, st, max_steps)
    intps = (a, b, cc)
    salidas = tuple(x["salida_hex"] for x in intps)
    pasos = tuple(x["pasos"] for x in intps)
    if c["esperado"] is None:
        veredicto = "FUERA_DE_DOMINIO"
    elif any(x["status"] != "HALTED" for x in intps):
        veredicto = "NO_HALTO"
    elif len(set(salidas)) != 1 or len(set(pasos)) != 1:
        veredicto = "DESACUERDO_ENTRE_INTERPRETES"
    elif salidas[0] == f"{c['esperado']:02x}":
        veredicto = "CORRECTO"
    else:
        veredicto = "INCORRECTO"
    return {"id": c["id"], "op": c["op"], "a": c["a"], "b": c["b"],
            "stream_hex": describe(st), "esperado": c["esperado"],
            "en_dominio_declarado": c["en_dominio_declarado"],
            "observado_hex": salidas[0], "pasos": pasos[0],
            "tres_vias_iguales": len(set(salidas)) == 1 and len(set(pasos)) == 1,
            "veredicto": veredicto, "A": a, "B": b, "C": cc}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["grid", "case", "run"])
    ap.add_argument("--op", choices=list(OPS))
    ap.add_argument("--a", type=int)
    ap.add_argument("--b", type=int)
    ap.add_argument("--max-steps", type=int, default=300_000)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv[1:])
    check_kernel()

    if a.mode == "grid":
        for c in casos():
            exp = "-" if c["esperado"] is None else f"{c['esperado']:02x}"
            print(f"{NOMBRE[c['op']]:12s} {c['a']} {c['b']}  esperado={exp}  "
                  f"{'dentro' if c['en_dominio_declarado'] else 'FUERA(declarado)'}")
        return 0
    if a.mode == "case":
        if a.op is None or a.a is None or a.b is None:
            print("error: case espera --op --a --b", file=sys.stderr)
            return 2
        print(describe(stream(a.op, a.a, a.b)))
        return 0
    if a.mode == "run":
        for exe in (ENGINE_A, ENGINE_B):
            if not exe.is_file():
                raise SystemExit(f"no existe el interprete: {exe}")
        mod = load_oracle_module()
        if mod.MEM_SIZE != LIMITE_CLASICO:
            raise SystemExit(f"el modelo C no es Clasico 3^10: MEM_SIZE={mod.MEM_SIZE}")
        src_text = KERNEL.read_text(encoding="ascii")
        planos = [one_case(mod, src_text, c, a.max_steps) for c in casos()]
        por_op = {}
        for op in OPS:
            fila = [x for x in planos if x["op"] == op]
            dentro = [x for x in fila if x["en_dominio_declarado"]]
            por_op[op] = {
                "total": len(fila),
                "correcto": sum(1 for x in fila if x["veredicto"] == "CORRECTO"),
                "incorrecto": sum(1 for x in fila if x["veredicto"] == "INCORRECTO"),
                "fuera_de_dominio": sum(1 for x in fila if x["veredicto"] == "FUERA_DE_DOMINIO"),
                "dentro_declarado_correctos": sum(1 for x in dentro if x["veredicto"] == "CORRECTO"),
                "dentro_declarado_total": len(dentro),
                "incorrecciones": [f"{x['a']},{x['b']} -> obs {x['observado_hex']} exp {x['esperado']:02x}"
                                   for x in fila if x["veredicto"] == "INCORRECTO"],
            }
        informe = {
            "objetivo": "auditar que pares de operandos calcula BIEN el kernel alu_rel_pass25, "
                        "mas alla del corpus sellado de 25 vectores",
            "kernel": {"archivo": str(KERNEL), "sha256": sha256(KERNEL),
                       "bytes": KERNEL.stat().st_size,
                       "margen_celdas": LIMITE_CLASICO - KERNEL.stat().st_size},
            "rejilla": {"op1": list(OP1), "op2": list(OP2)},
            "interpretes": {"A": str(ENGINE_A), "B": str(ENGINE_B), "C": str(ORACLE_C_SRC)},
            "max_steps": a.max_steps,
            "desacuerdos_entre_interpretes": sum(1 for x in planos
                                                 if not x["tres_vias_iguales"]),
            "resumen_por_opcode": por_op,
            "casos": planos,
        }
        texto = json.dumps(informe, indent=2, ensure_ascii=False) + "\n"
        if a.out:
            Path(a.out).write_text(texto, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(texto)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
