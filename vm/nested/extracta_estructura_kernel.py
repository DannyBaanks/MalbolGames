#!/usr/bin/env python3
"""extracta_estructura_kernel.py — extrae del HeLL upstream la mecanica que explica el negativo.

Carga en memoria (solo lectura, sin ejecutar el build) el modulo
`MALBOLGE-MB-DATABASE/vm_malbolge/tools/mbir_alu_rel_gen.py`, llama a su `generate()` y emite el
subconjunto de lineas de HeLL que muestra COMO se produce un resultado en el kernel ALU_REL: las
etiquetas de clasificacion (`sum_is_*`, `diff_is_*`, `load_*`), las constantes `ROT` que
materializan el byte impreso y la cadena de decrementos que decide que etiqueta se toma.

Por que hace falta: `audit_alu_rel_isa.py` es una MEDIDA. Este archivo da el MECANISMO observable
en el codigo, para que la conclusion no dependa de adivinar por que el kernel acierta solo en un
dominio diminuto. No escribe nada, no ensambla nada, no ejecuta la VM.

Nota tecnica: `SOURCE_HELL` es UNA sola linea de Python con saltos escapados, por eso se usa
`generate()` en vez de leer el .py linea a linea.

Uso:
    extracta_estructura_kernel.py            > stdout
    extracta_estructura_kernel.py -o FILE    > a FILE (LF)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import sys
from pathlib import Path

SRC = (Path(__file__).resolve().parents[2].parent / "MALBOLGE-MB-DATABASE"
       / "vm_malbolge" / "tools" / "mbir_alu_rel_gen.py")
RUTAS = ("sum_is_", "diff_is_", "load_sum_", "load_diff_", "check_results", "cmp_diff_",
         "op2_is_", "op2_nonzero", "check_add_or_sub_high", "return_from_dec_op",
         "add_rst0_done", "add_val_clean", "NO_MORE_CARRY_FLAG", "ROT ")


def load_module():
    spec = importlib.util.spec_from_file_location("mbir_alu_rel_gen_upstream", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv[1:])
    if not SRC.is_file():
        print(f"no existe el fuente upstream: {SRC}", file=sys.stderr)
        return 1
    sha_src = hashlib.sha256(SRC.read_bytes()).hexdigest()
    mod = load_module()
    hell = mod.generate()
    sha_hell = hashlib.sha256(hell.encode("utf-8")).hexdigest()
    lineas = hell.splitlines()
    out = [f"# HeLL generado por {SRC}",
           f"# sha256 del fuente del generador: {sha_src}",
           f"# sha256 del HeLL generado: {sha_hell}   ({len(hell.encode())} bytes, "
           f"{len(lineas)} lineas)",
           "# solo lectura: el arbol upstream no se toco en esta campana",
           "# lineas que deciden COMO se materializa un resultado:", ""]
    tomados = 0
    for n, l in enumerate(lineas, 1):
        if any(r in l for r in RUTAS):
            out.append(f"{n:5d}| {l}")
            tomados += 1
    enteros = sorted({int(m) for m in re.findall(r"ROT (\d+)\b", hell)})
    cnot = sorted({m for m in re.findall(r"ROT (C\d|C2\d)\b", hell)})
    etiquetas = sorted({m.group(0) for m in re.finditer(r"(?:sum|diff)_is_\w+", hell)})
    salidas = sorted({m.group(0) for m in re.finditer(r"load_\w+", hell)})
    out += ["", f"# etiquetas de resultado: {etiquetas}",
            f"# subrutinas que empujan el resultado: {salidas}",
            f"# constantes ROT enteras: {enteros}",
            f"# constantes ROT en notacion C: {cnot}",
            f"# lineas seleccionadas: {tomados} de {len(lineas)}",
            "", "# LECTURA: el resultado NO es un entero calculado, es una de un numero finito de",
            "# etiquetas de clasificacion, cada una materializada por UNA constante ROT. Eso acota",
            "# el vocabulario de bytes imprimibles del kernel, y es lo que mide el informe de rejilla."]
    texto = "\n".join(out) + "\n"
    if a.out:
        Path(a.out).write_text(texto, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
