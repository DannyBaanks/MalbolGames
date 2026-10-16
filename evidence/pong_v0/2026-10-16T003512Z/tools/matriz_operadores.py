#!/usr/bin/env python3
"""matriz_operadores.py — deriva la lectura estructural de un informe `audit_alu_rel_isa.py run`.

Lee el JSON del informe y escupe, en texto plano para el evidence:

  1. la matriz op1 x op2 de lo OBSERVADO, con `*` donde no coincide con la aritmetica entera,
  2. el VOCABULARIO de bytes que el kernel sabe imprimir por opcode (esto es lo que decide si
     el dominio de `pong1` es expresable: si 3 y 4 no estan, el tablero 8x4 no cabe),
  3. la diagonal `a == a` de CMP_EQ, que es la que la puerta de gol necesita,
  4. la interseccion entre el vocabulario imprimible y los valores que el tick necesita
     (`by`, `pl`, `ny` en 0..3 y el bit 0/1 de la puerta).

No ejecuta la VM: es un analisis determinista sobre evidencia ya sellada en el JSON.

Uso:
    matriz_operadores.py <informe.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

VALORES_TICK = (0, 1, 2, 3)                                   # by, pl, ny en tablero 8x4


def matriz(casos: list[dict], op: str, xs: list[int], ys: list[int]) -> list[str]:
    idx = {c["id"]: c for c in casos if c["op"] == op}
    lineas = [f"     op2 ->  {'   '.join(f'{b:>4d}' for b in ys)}"]
    for a in xs:
        cel = []
        for b in ys:
            c = idx.get(f"{op}_{a}_{b}")
            if c is None:
                cel.append("   -- ")
                continue
            marca = "" if c["veredicto"] == "CORRECTO" else "*"
            cel.append(f"{c['observado_hex'] + marca:>5}")
        esperado = "  ".join(
            f'{idx[f"{op}_{a}_{b}"]["esperado"]:02x}' for b in ys if f"{op}_{a}_{b}" in idx)
        lineas.append(f"  op1 {a}:  " + "  ".join(cel) + f"      esperado: {esperado}")
    return lineas


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: matriz_operadores.py <informe.json>", file=sys.stderr)
        return 2
    informe = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    casos = informe["casos"]
    xs = informe["rejilla"]["op1"]
    ys = informe["rejilla"]["op2"]
    out: list[str] = []
    out.append(f"informe: {argv[1]}")
    out.append(f"rejilla: op1={xs} x op2={ys}   desacuerdos entre interpretes="
               f"{informe['desacuerdos_entre_interpretes']}")
    out.append("")
    for op in ("ADD", "SUB", "CMPEQ"):
        sub = [c for c in casos if c["op"] == op]
        vocab = sorted({c["observado_hex"] for c in sub})
        r = informe["resumen_por_opcode"][op]
        out.append(f"== {op}  correcto {r['correcto']}/{r['total']}   "
                   f"vocabulario imprimible medido = {vocab}")
        out.extend(matriz(casos, op, xs, ys))
        out.append("")
    diag = [c for c in casos if c["op"] == "CMPEQ" and c["a"] == c["b"]]
    out.append("== CMP_EQ en la diagonal a == a (lo que la puerta de gol necesita)")
    for c in diag:
        out.append(f"   {c['a']} == {c['b']}: observado {c['observado_hex']}  "
                   f"esperado 01  -> {c['veredicto']}")
    ok = {c["a"] for c in diag if c["veredicto"] == "CORRECTO"}
    out.append(f"   la diagonal acierta SOLO en op1 = {sorted(ok)}")
    out.append("")
    vocab_total = sorted({c["observado_hex"] for c in casos})
    enteros = sorted({int(v, 16) for v in vocab_total})
    out.append(f"vocabulario TOTAL de bytes que el kernel imprime = {vocab_total} "
               f"= enteros {enteros}")
    faltan = [v for v in VALORES_TICK if v not in enteros]
    out.append(f"valores del tick `pong1` (0..3) NO imprimibles: {faltan}")
    out.append("=> si la lista no es vacia, el dominio del tablero 8x4 NO es expresable como "
               "resultado de este kernel, con independencia del stream que se le de.")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
