#!/usr/bin/env python3
"""Pruebas de contrato del oraculo PONG_V0 (harness G1).

No compara C contra Python: eso lo hace harness/compare_oracle.py. Este archivo prueba
propiedades del CONTRATO sobre cada oráculo por separado:

  T1  determinismo: la misma entrada produce los mismos bytes N veces
  T2  higiene de bytes: salida LF exclusivo, sin CR, sin BOM, sin depuracion mezclada
  T3  fallo cerrado: entrada invalida => exit != 0 y CERO bytes en stdout
  T4  composición: step aplicado en secuencia == chain de una sola pasada
  T5  saturacion y rangos: marcador 99 no sube, tick no envuelve, paleta se clampa
  T6  rechazo del tick maximo: 2^31-1 + 1 es fallo, no envoltura

    python3 tests/test_oracle.py [--root DIR]

docs/PONG_MIN_SPEC.md par. 3, 4, 5, 8.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

MAX_TICK = 2**31 - 1


def drive(cmd: list[str], mode: str, stdin: str) -> tuple[int, bytes]:
    p = subprocess.run(cmd + [mode], input=stdin.encode("ascii"),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout


def oracles(root: Path) -> dict[str, list[str]]:
    return {
        "py": [sys.executable, str(root / "oracle" / "pong_reference.py")],
        "c": [str(root / "build" / "pong_reference")],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    parsed = ap.parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(parsed.root).resolve()
    fails: list[str] = []

    def want(tag: str, cond: bool, detail: str = ""):
        if not cond:
            fails.append(f"{tag} [{oracle_name}]: {detail}")

    for oracle_name, cmd in oracles(root).items():
        if oracle_name == "c" and not Path(cmd[0]).is_file():
            fails.append(f"precondicion [{oracle_name}]: no existe {cmd[0]}")
            continue

        # T1 determinismo
        line = "pong1;8,4,4,2,1,-1,0,0,0,0,0;0,0\n"
        shots = {drive(cmd, "step", line)[1] for _ in range(25)}
        want("T1 determinismo", len(shots) == 1, f"{len(shots)} salidas distintas")

        # T2 higiene de bytes
        rc, out = drive(cmd, "render", "pong1;8,4,2,2,1,-1,0,3,1,2,5\n")
        want("T2 rc", rc == 0, f"rc={rc}")
        want("T2 sin CR", b"\r" not in out, out[:40].hex())
        want("T2 sin BOM", not out.startswith(b"\xef\xbb\xbf"), out[:8].hex())
        want("T2 LF final", out.endswith(b"\n"), out[-8:])
        want("T2 lineas = filas", out.count(b"\n") == 4, f"{out.count(chr(10).encode())} lineas")

        # T3 fallo cerrado
        bad = [
            "pong1;8,4,4,2,1,-1,0,0,0,0,0",          # estado sin movimientos
            "pong1;8,4,4,2,1,-1,0,0,0,0,0;0,0,0",    # 3 movimientos
            "pong1;8,4,4,2,2,-1,0,0,0,0,0;0,0",      # velocidad no +-1
            "PONG1;8,4,4,2,1,-1,0,0,0,0,0;0,0",      # prefijo no canonico
            "pong1;8,4,4,2,1,-1,0,0,0,0,0;+0,0",     # signo redundante
            "",                                       # vacio
        ]
        for b in bad:
            rc, out = drive(cmd, "step", b + "\n")
            want("T3 fallo cerrado", rc != 0 and out == b"", f"stdin={b!r} rc={rc} stdout={out!r}")

        # T4 composicion: step sucesivo == chain
        s0 = "pong1;8,4,4,2,1,-1,0,0,0,0,0"
        moves = ["0,0", "1,0", "-1,0", "0,0"]
        seq = [s0]
        cur = s0
        for m in moves:
            rc, out = drive(cmd, "step", f"{cur};{m}\n")
            want("T4 paso intermedio", rc == 0, f"rc={rc}")
            cur = out.decode("ascii").rstrip("\n")
            seq.append(cur)
        chain_in = seq[0] + "\n" + "\n".join(
            f"{seq[i]};{moves[i]}" for i in range(len(moves))
        ) + "\n"
        rc, chain_out = drive(cmd, "chain", chain_in)
        want("T4 chain rc", rc == 0, f"rc={rc}")
        want("T4 chain == pasos", chain_out == ("\n".join(seq[1:]) + "\n").encode("ascii"),
             chain_out[:120].decode("ascii", "replace"))

        # T5 saturacion / clamp / tick monotono
        rc, out = drive(cmd, "step", "pong1;8,4,7,3,1,1,0,0,99,0,0;0,0\n")
        want("T5 marcador saturado", out.decode().split(";")[1].split(",")[8] == "99", out)
        rc, out = drive(cmd, "step", "pong1;8,4,4,2,1,-1,3,0,0,0,0;1,0\n")
        want("T5 paleta clampeada", out.decode().split(";")[1].split(",")[6] == "3", out)

        # T6 tick maximo: sin envoltura
        rc, out = drive(cmd, "step", f"pong1;8,4,4,2,1,-1,0,0,0,0,{MAX_TICK};0,0\n")
        want("T6 tick maximo rechazado", rc != 0 and out == b"", f"rc={rc} stdout={out!r}")

    print(f"test_oracle: {len(fails)} fallos -> {'PASS' if not fails else 'FAIL'}")
    for f in fails:
        print("  " + f, file=sys.stderr)
    return 1 if fails else 0


def test_oracle_contract():
    assert main([]) == 0


if __name__ == "__main__":
    sys.exit(main())
