#!/usr/bin/env python3
"""run_handoff.py — gate G3 de MALGAMES/PONG_V0: una ejecucion Malbolge lee el byte de otra.

Que se reclama (y que NO)
-------------------------
Se reclama UN edge: `A(.mb) -> stdout -> stdin -> B(.mb)` dentro de la VM Malbolge Clasica.
El host escribe UN byte (la entrada de A) y entre las dos ejecuciones hay UNA operacion de
tuberia real de shell: lo que B lee con su propio `IN` son los bytes que A escribio. El host
no re-codifica nada en el medio, porque no intervene el tramo.

Dos modos, mismo edge con dos productores:

    modo nota  A-raw (nuevo, emite 0x01/0x02)  ->  B-NOTA (3 rutas)   composicion NOT(bounce)
    modo eco   A sellado de G2 (emite '0'/'1') ->  B-ECO (fallback)    composicion bounce

No se reclama un tick, ni un frame, ni un juego: son DOS funciones encadenadas UNA vez, cada
una sobre un dominio finito. La expectativa se deriva del oraculo
`oracle/pong_reference.py`, nunca de la VM.

CONDICIONES (pactadas ANTES de correr, inmoviles para esta corrida)
-------------------------------------------------------------------
 C1  Cada x del dominio: salida de B por tuberia == la composicion derivada del oraculo.
 C2  Las cuatro parejas de interpretes (A,B) en {E1,E2}^2 coinciden en salida Y en pasos.
 C3  Los bytes que circularon por la tuberia (capturados con `tee`) == el stdout crudo de A
     ejecutado solo, y == el byte que se esperaba que A emitiera. Prueba de que el byte viajo.
 C4  A solo: E1 == E2 == modelo C en salida y pasos (la via de tres que ya usa G2).
 C5  B alimentado DIRECTAMENTE por el host con ese mismo byte == B por tuberia, en salida y en
     PASOS. Como el modo tuberia entrega ademas el 0x0A del runner y el directo no, la
     igualdad de pasos demuestra que ese byte de framing nunca entra en el computo de B.
 C6  B con stdin VACIO (EOF) no emite ningun byte de programa: B no puede inventar el bit.
 C7  Selectividad, por modo:
     nota — el mutante B-swap (misma A, misma tuberia) invierte los 8 casos.
     eco    — (a) la composicion toma los dos valores '0' y '1' (no es una constante),
              (b) B-ECO con 0x30 y con 0x31 da salidas distintas (es inyectivo en su stdin),
              (c) B-ECO con 0x01 emite 'P': la ruta de despacho existe y NO es la que corrio,
                  luego el edge paso por el fallback de eco.
PASS por caso exige C1..C7. Exit 0 exige TODOS los casos PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import pong_codegen as cg                                # noqa: E402
import run_classic as rc                                 # noqa: E402
import handoff_codegen as hc                             # noqa: E402

E1 = rc.ENGINE_A
E2 = rc.ENGINE_B
STEPS = re.compile(r"steps:\s*(\d+)\s*\|\s*status:\s*([A-Z_]+)")

MODES = {
    "nota": {
        "a": "pong_bounce_raw_v0.mb",
        "b": "pong_not_v0.mb",
        "mut": "pong_not_v0_MUTANT_swap.mb",
        "negate": True,
        "byte": lambda bit: bytes([hc.RAW_FOR_BIT[bit]]),
        "reclamo": "B calcula NOT sobre el byte que A imprimio",
    },
    "eco": {
        "a": "pong_bounce_v0.mb",                        # SELLADO por G2: solo se lee/ejecuta
        "b": "pong_echo_v0.mb",
        "mut": None,                                    # usa la sonda C7 del modo eco
        "negate": False,
        "byte": lambda bit: bytes([0x30 + bit]),
        "reclamo": "el byte del artefacto sellado viaja y B lo reimprime tal cual",
    },
}

CONDICIONES = [c for c in __doc__.split("CONDICIONES")[1].split("PASS por caso")[0].strip().splitlines() if c.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_steps(err: bytes) -> tuple[int | None, str | None]:
    m = STEPS.search(err.decode("utf-8", "replace"))
    return (int(m.group(1)) if m else None, m.group(2) if m else None)


def pipe_run(exe_a: Path, a_mb: Path, exe_b: Path, b_mb: Path, one_byte: bytes,
             max_steps: int, workdir: Path, tag: str) -> dict:
    """Una sola operacion de tuberia real: A stdin=byte -> stdout | tee | B stdin -> stdout."""
    bin_in = workdir / f"{tag}.in"
    bin_in.write_bytes(one_byte)
    a_out = workdir / f"{tag}.Aout"
    b_out = workdir / f"{tag}.Bout"
    a_err = workdir / f"{tag}.Aerr"
    b_err = workdir / f"{tag}.Berr"
    script = (f"set -o pipefail; {shlex.quote(str(exe_a))} {shlex.quote(str(a_mb))} "
              f"{max_steps} < {shlex.quote(str(bin_in))} 2> {shlex.quote(str(a_err))} "
              f"| tee {shlex.quote(str(a_out))} "
              f"| {shlex.quote(str(exe_b))} {shlex.quote(str(b_mb))} {max_steps} "
              f"> {shlex.quote(str(b_out))} 2> {shlex.quote(str(b_err))}")
    p = subprocess.run(["bash", "-c", script], timeout=900)
    a_bytes = a_out.read_bytes()
    b_bytes = b_out.read_bytes()
    bp, bs = parse_steps(b_err.read_bytes())
    ap, as_ = parse_steps(a_err.read_bytes())
    return {
        "cmd": script,
        "rc": p.returncode,
        "A_stdout_bytes_hex": a_bytes.hex(),
        "A_pasos": ap, "A_status": as_,
        "flujo_tuberia_hex": a_bytes.hex(),
        "B_stdout_raw_hex": b_bytes.hex(),
        "B_salida": rc.deframe(b_bytes).decode("latin-1"),
        "B_pasos": bp, "B_status": bs,
        "B_stderr": b_err.read_bytes().decode("utf-8", "replace").strip(),
    }


def direct_run(exe: Path, mb: Path, feed: bytes, max_steps: int) -> dict:
    p = subprocess.run([str(exe), str(mb), str(max_steps)], input=feed,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    st, ss = parse_steps(p.stderr)
    return {"feed_hex": feed.hex(), "stdout_raw_hex": p.stdout.hex(),
            "salida": rc.deframe(p.stdout).decode("latin-1"),
            "pasos": st, "status": ss, "rc": p.returncode}


def decode_known(op: int, kind: str) -> str:
    if kind == "bounce":
        by, vy = cg.decode_bounce(op)
        return f"by={by}, vy={vy:+d}"
    pl, by = cg.decode_contact(op)
    return f"pl={pl}, by={by}"


def one_case(mode: str, kind: str, op: int, expect: str, raw_byte: bytes, a_mb: Path,
             b_mb: Path, mut_mb: Path | None, model, src_a: str, src_b: str,
             max_steps: int, workdir: Path) -> dict:
    one_byte = bytes([op])
    tuberias = {name: pipe_run(ea, a_mb, eb, b_mb, one_byte, max_steps, workdir, f"{op:02x}_{name}")
                for name, ea, eb in (("E1E1", E1, E1), ("E1E2", E1, E2),
                                     ("E2E1", E2, E1), ("E2E2", E2, E2))}
    mut = pipe_run(E1, a_mb, E1, mut_mb, one_byte, max_steps, workdir, f"{op:02x}_MUT") \
        if mut_mb else None
    solo_a = {"E1": rc.run_native(E1, a_mb, one_byte, max_steps),
              "E2": rc.run_native(E2, a_mb, one_byte, max_steps),
              "C": rc.run_model(model, src_a, one_byte, max_steps)}
    crudo = raw_byte.decode("latin-1")
    solo_b = {"E1": direct_run(E1, b_mb, raw_byte, max_steps),
              "E2": direct_run(E2, b_mb, raw_byte, max_steps),
              "C": rc.run_model(model, src_b, raw_byte, max_steps)}
    eof_b = direct_run(E1, b_mb, b"", max_steps)

    salidas_tub = {k: v["B_salida"] for k, v in tuberias.items()}
    pasos_tub = {k: v["B_pasos"] for k, v in tuberias.items()}
    esperada_cruda = (raw_byte + b"\n").hex()

    c1 = all(s == expect for s in salidas_tub.values())
    c2 = len(set(salidas_tub.values())) == 1 and len(set(pasos_tub.values())) == 1
    c3 = (all(v["flujo_tuberia_hex"] == esperada_cruda for v in tuberias.values())
          and solo_a["E1"]["stdout_raw_hex"] == esperada_cruda
          and solo_a["E2"]["stdout_raw_hex"] == esperada_cruda)
    c4 = (len({solo_a["E1"]["salida"], solo_a["E2"]["salida"], solo_a["C"]["salida"]}) == 1
          and solo_a["E1"]["salida"] == crudo
          and len({solo_a["E1"]["pasos"], solo_a["E2"]["pasos"], solo_a["C"]["pasos"]}) == 1)
    c5 = (solo_b["E1"]["salida"] == salidas_tub["E1E1"]
          and solo_b["E2"]["salida"] == salidas_tub["E2E2"]
          and solo_b["E1"]["pasos"] == pasos_tub["E1E1"]
          and solo_b["E2"]["pasos"] == pasos_tub["E2E2"]
          and solo_b["C"]["salida"] == expect
          and solo_b["C"]["pasos"] == solo_b["E1"]["pasos"])
    c6 = eof_b["salida"] == ""

    if mode == "nota":
        c7 = mut is not None and mut["B_salida"] == str(1 - int(expect))
        sonda = {"mutante_swap": mut}
    else:
        # la composicion del modo eco toma los dos valores y B-ECO es inyectivo en stdin;
        # sonda aparte: 0x01 debe dar 'P' (ruta de despacho) para probar que el edge NO por ahi
        otras = {f"{o:02x}": direct_run(E1, b_mb, bytes([o]), max_steps) for o in (0x01,)}
        opuestos = direct_run(E1, b_mb, bytes([0x30 + 0x31 - raw_byte[0]]), max_steps)
        c7 = (opuestos["salida"] != expect
              and otras["01"]["salida"] == "P"
              and expect in ("0", "1"))
        sonda = {"B_eco_otro_byte": opuestos, "B_eco_sonda_0x01": otras["01"]}

    checks = {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5, "C6": c6, "C7": c7}

    if any(s == "" for s in salidas_tub.values()):
        veredicto = "SIN_SALIDA"
    elif any(v["B_status"] != "HALTED" for v in tuberias.values()):
        veredicto = "NO_HALTO"
    elif any(p is not None and p >= max_steps for p in pasos_tub.values()):
        veredicto = "MAX_PASOS"
    elif not all(checks.values()):
        veredicto = "DESCUADRE"
    else:
        veredicto = "PASS"
    return {
        "opcode": f"{op:02x}",
        "decodificado": decode_known(op, kind),
        "esperado_oraculo": expect,
        "byte_crudo_esperado": raw_byte.hex(),
        "tuberias": tuberias,
        "A_solo": solo_a,
        "B_solo_directo": solo_b,
        "B_stdin_vacio": eof_b,
        "sondas_selectividad": sonda,
        "condiciones": checks,
        "veredicto": veredicto,
    }


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="nota", choices=sorted(MODES))
    ap.add_argument("--kind", default="bounce", choices=list(cg.KINDS))
    ap.add_argument("--a", default=None, help="override del productor (ruta .mb)")
    ap.add_argument("--b", default=None, help="override del receptor (ruta .mb)")
    ap.add_argument("--max-steps", type=int, default=2_000_000)
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--keep-raw", default=None,
                    help="directorio donde copiar los stdout/stderr crudos de cada caso")
    a = ap.parse_args(argv[1:])

    m = MODES[a.mode]
    a_mb = Path(a.a) if a.a else HERE.parent / m["a"]
    b_mb = Path(a.b) if a.b else HERE.parent / m["b"]
    mut_mb = Path(m["mut"]).resolve() if m["mut"] else None
    for p in filter(None, (a_mb, b_mb, mut_mb, E1, E2)):
        if not p.is_file():
            sys.exit(f"no existe el archivo: {p}")
    src_a = a_mb.read_text(encoding="ascii")
    src_b = b_mb.read_text(encoding="ascii")
    model = rc.load_oracle_module()
    if model.MEM_SIZE != rc.MEM_SIZE:
        sys.exit(f"el modelo C no es Clasico 3^10: MEM_SIZE={model.MEM_SIZE}")

    table = cg.marker_table(a.kind)
    expect = hc.expect_composition(a.kind, negate=m["negate"])
    domain = cg.domain(a.kind)
    with tempfile.TemporaryDirectory(prefix="g3_") as td:
        workdir = Path(td)
        casos = [one_case(a.mode, a.kind, op, expect[op],
                          m["byte"](int(table[op])), a_mb, b_mb, mut_mb,
                          model, src_a, src_b, a.max_steps, workdir)
                 for op, _ in domain]
        hashes_raw = {}
        if a.keep_raw:
            kd = Path(a.keep_raw)
            kd.mkdir(parents=True, exist_ok=True)
            for f in sorted(workdir.iterdir()):
                data = f.read_bytes()
                (kd / f.name).write_bytes(data)
                hashes_raw[f.name] = hashlib.sha256(data).hexdigest()

    n_ok = sum(1 for x in casos if x["veredicto"] == "PASS")
    informe = {
        "experimento": f"G3 handoff modo {a.mode} — {a_mb.name} -> stdin -> {b_mb.name} "
                       f"dentro de la VM Clasica ({m['reclamo']})",
        "modo": a.mode,
        "predicado": a.kind,
        "tablero": f"{cg.BOARD_W}x{cg.BOARD_H}",
        "condiciones_pactadas_antes_de_correr": CONDICIONES,
        "artefactos": {
            "A": {"ruta": str(a_mb), "sha256": sha256(a_mb), "bytes": a_mb.stat().st_size},
            "B": {"ruta": str(b_mb), "sha256": sha256(b_mb), "bytes": b_mb.stat().st_size},
            "B_mutante": ({"ruta": str(mut_mb), "sha256": sha256(mut_mb),
                           "bytes": mut_mb.stat().st_size} if mut_mb else None),
            "celdas_clasico": rc.MEM_SIZE,
        },
        "interpretes": {"E1": str(E1), "E2": str(E2), "modelo_C": str(rc.ORACLE_C_SRC)},
        "max_steps": a.max_steps,
        "dominio_puntos": len(domain),
        "expect_oraculo": {f"{op:02x}": expect[op] for op, _ in domain},
        "pass": n_ok,
        "casos": casos,
        "todo_pass": n_ok == len(domain),
    }
    if a.keep_raw:
        informe["sha256_crudos"] = hashes_raw
    texto = json.dumps(informe, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).write_text(texto, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(texto)
    return 0 if informe["todo_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
