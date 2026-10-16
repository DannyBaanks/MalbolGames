#!/usr/bin/env python3
"""Comparador de oraculos MALGAMES/PONG_V0 (harness G1).

Ejecuta el oracula Python y el oracula C sobre los mismos fixtures congelados y exige:

  1. igualdad byte a byte entre stdout(C) y stdout(PY) para cada caso,
  2. igualdad byte a byte contra los bytes esperados del fixture,
  3. mismo exit status (0 para casos validos, distinto de 0 con stdout vacio para rechazos).

Un stdout no vacio en un caso de rechazo es un fallo: el contrato dice que una entrada invalida
no produce salida. La salida de este programa es JSON puro, sin depuracion mezclada.

    python3 harness/compare_oracle.py [--root DIR]

docs/PONG_MIN_SPEC.md par. 3 y par. 8.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

FIX = "tests/fixtures"


def run(binary: list[str], stdin: bytes) -> tuple[int, bytes, bytes]:
    p = subprocess.run(binary, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout, p.stderr


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def rows(path: Path) -> list[list[str]]:
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line == "":
            continue
        out.append(line.split("\t"))
    return out


def unescape(s: str) -> bytes:
    return s.replace("\\n", "\n").encode("ascii")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    py = [sys.executable, str(root / "oracle" / "pong_reference.py")]
    cbin = root / "build" / "pong_reference"
    if not cbin.is_file():
        print(json.dumps({"error": f"no existe el binario C: {cbin}"}), file=sys.stderr)
        return 3
    c = [str(cbin)]

    checks: list[dict] = []
    failures = 0

    def check(kind: str, case: str, mode: str, stdin: bytes, expected: bytes, must_reject: bool):
        nonlocal failures
        rc_p, so_p, _ = run(py + [mode], stdin)
        rc_c, so_c, _ = run(c + [mode], stdin)
        if must_reject:
            ok = rc_p != 0 and rc_c != 0 and so_p == b"" and so_c == b""
            detail = f"rc PY={rc_p} C={rc_c} stdout={len(so_p)}/{len(so_c)} bytes"
        else:
            ok = (
                rc_p == 0
                and rc_c == 0
                and so_p == expected
                and so_c == expected
                and so_p == so_c
            )
            detail = (
                f"rc PY={rc_p} C={rc_c}; sha PY={sha(so_p)[:16]} C={sha(so_c)[:16]} "
                f"expected={sha(expected)[:16]}"
            )
        if not ok:
            failures += 1
        checks.append(
            {
                "kind": kind,
                "case": case,
                "mode": mode,
                "stdin_sha256": sha(stdin),
                "expected_sha256": sha(expected),
                "py_stdout_sha256": sha(so_p),
                "c_stdout_sha256": sha(so_c),
                "py_rc": rc_p,
                "c_rc": rc_c,
                "verdict": "PASS" if ok else "FAIL",
                "detail": detail,
            }
        )

    # 1. transiciones: linea de trabajo -> estado siguiente
    for rid, _name, estado, mov, want in rows(Path(root) / FIX / "transitions.tsv")[1:]:
        stdin = f"{estado};{mov}\n".encode("ascii")
        check("transition", rid, "step", stdin, (want + "\n").encode("ascii"), False)

    # 2. renders: estado -> frame
    for rid, _name, estado, frame in rows(Path(root) / FIX / "frames.tsv")[1:]:
        check("render", rid, "render", (estado + "\n").encode("ascii"), unescape(frame), False)

    # 3. cadenas: bytes exactos de entrada -> bytes exactos de salida
    for inp in sorted(Path(root).glob(FIX + "/chain_*.in")):
        exp = inp.with_suffix(".expected").read_bytes()
        check("chain", inp.name[:-3], "chain", inp.read_bytes(), exp, False)

    # 4. rechazos de una linea: todos se presentan al modo step, que exige linea de trabajo
    #    completa ('pong1;<11>;<lm>,<rm>'); un estado solo tambien es invalida para step.
    for line in (Path(root) / FIX / "rejects.txt").read_text(encoding="utf-8").split("\n"):
        if line == "":
            continue
        check("reject", sha(line.encode("ascii"))[:12], "step", (line + "\n").encode("ascii"), b"", True)

    # 5. rechazos de cadena (bloque separado por ---)
    blocks = [
        b for b in (Path(root) / FIX / "chain_rejects.txt").read_text(encoding="utf-8").split("\n---\n")
    ]
    for i, blk in enumerate(blocks, 1):
        if blk.strip() == "":
            continue
        check("chain_reject", f"K{i}", "chain", (blk.rstrip("\n") + "\n").encode("ascii"), b"", True)

    verdict = "PASS" if failures == 0 else "FAIL"
    print(
        json.dumps(
            {
                "tool": "compare_oracle",
                "gates": "G1",
                "checks_total": len(checks),
                "checks_passed": len(checks) - failures,
                "failures": failures,
                "verdict": verdict,
                "byte_equal_cross_oracle": all(
                    x["py_stdout_sha256"] == x["c_stdout_sha256"] for x in checks
                ),
                "checks": checks,
            },
            indent=2,
        )
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
