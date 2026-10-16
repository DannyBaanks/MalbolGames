#!/usr/bin/env python3
"""probe_hell_bytes.py — sonda de bytes crudos para el gate G3 (handoff) de MALGAMES/PONG_V0.

Responde por MEDICION, no por lectura de docs, a las tres preguntas que deciden el alfabeto
de handoff entre dos ejecuciones Malbolge:

    markers    : que expresion de HeLL hace que `OUT` emita un byte NO imprimible (0x01, 0x02).
                 Se ensamblan variantes del despacho de 3 rutas de upstream cambiando solo la
                 linea `ROT (...)` de la ruta 0x01 y se lee el hex que imprime cada interprete.
    receivers  : que hace el receptor con cada byte posible: 0x00 (HALT), 0x01/0x02 (rutas de
                 despacho), 0x30/0x31 (fuera de tabla -> fallback de eco) y EOF (stdin vacio).
    ascii      : contraste del artefacto SELLADO de G2: el alfabeto que sale hoy por stdout.

Upstream se usa SOLO en lectura (generar el .hell base con su propia CLI). Todo se escribe en
un directorio temporal; nada toca MALBOLGE-MB-DATABASE ni los artefactos sellados.

Uso:
    python3 probe_hell_bytes.py markers
    python3 probe_hell_bytes.py receivers
    python3 probe_hell_bytes.py ascii
Salida: JSON puro en stdout. Exit 0 si la sonda respondio (no afirma el resultado).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import pong_codegen as cg                                # noqa: E402
import run_classic as rc                                 # noqa: E402
import handoff_codegen as hc                             # noqa: E402

LMAO = cg.REPO.parent / "MALBOLGE-MB-DATABASE" / "third_party" / "lmao" / "lmao"
GEN = cg.UPSTREAM
STEPS = re.compile(r"steps:\s*(\d+)\s*\|\s*status:\s*([A-Z_]+)")

# candidatos a expresion de marcador: el lexer de HeLL solo permite literales de caracter
# imprimibles (0x20..0x7E), asi que la unica esperanza para un byte crudo es la constante
# decimal o ternaria. `<< 1` es ROTATE_L ternario (no un shift de bits): ver src/lmao.y.
CANDIDATES = ["('1' << 1)", "(1 << 1)", "1", "(1 >> 1)", "C1", "C2",
              "(0t1 << 1)", "(0t2 << 1)", "(0t11 << 1)", "(C2!1)", "(1!C2)"]


def gen3(workdir: Path) -> Path:
    """Dispatch de 3 rutas generado por la CLI upstream, intacto (marcadores P/R)."""
    out = workdir / "b3.hell"
    subprocess.run([sys.executable, str(GEN), "--opcodes", "000102", "-o", str(out)],
                   check=True, capture_output=True)
    return out


def asm(src: Path, dst: Path) -> int:
    p = subprocess.run([str(LMAO), "-o", str(dst), str(src)], capture_output=True, text=True)
    return p.returncode


def run(exe: Path, mb: Path, feed: bytes, max_steps: int = 2_000_000) -> dict:
    p = subprocess.run([str(exe), str(mb), str(max_steps)], input=feed,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    m = STEPS.search(p.stderr.decode("utf-8", "replace"))
    return {"feed_hex": feed.hex(), "stdout_raw_hex": p.stdout.hex(),
            "pasos": int(m.group(1)) if m else None,
            "status": m.group(2) if m else None, "rc": p.returncode}


def probe_markers() -> dict:
    base = gen3(Path(tmp.name)).read_text(encoding="utf-8")
    old = "\tROT ('P' << 1) R_ROT\n"
    assert base.count(old) == 1, f"linea de marcador no unica: {base.count(old)}"
    filas = []
    for cand in CANDIDATES:
        src = Path(tmp.name) / "p.hell"
        dst = Path(tmp.name) / "p.mb"
        src.write_text(base.replace(old, "\tROT %s R_ROT\n" % cand), encoding="utf-8")
        rc_asm = asm(src, dst)
        if rc_asm != 0:
            filas.append({"expresion": cand, "ensamble": "FALLO", "rc": rc_asm})
            continue
        e1 = run(rc.ENGINE_A, dst, b"\x01")
        e2 = run(rc.ENGINE_B, dst, b"\x01")
        filas.append({"expresion": cand, "ensamble": "OK", "mb_bytes": dst.stat().st_size,
                      "E1": e1, "E2": e2,
                      "coinciden": e1["stdout_raw_hex"] == e2["stdout_raw_hex"]
                      and e1["pasos"] == e2["pasos"]})
    return {"sonda": "markers", "pregunta": "que emite OUT para cada forma de constante HeLL",
            "entrada": "0x01 (ruta dispatch_01 del despacho de 3 rutas)", "casos": filas}


def probe_receivers() -> dict:
    wd = Path(tmp.name)
    nota = wd / "not.hell"
    nota.write_text(hc.header_b("nota") + hc.emit_b("nota"), encoding="utf-8")
    eco = wd / "eco.hell"
    eco.write_text(hc.header_b("eco") + hc.emit_b("eco"), encoding="utf-8")
    out = {}
    for nombre, src in (("B_nota", nota), ("B_eco", eco)):
        dst = wd / f"{nombre}.mb"
        if asm(src, dst) != 0:
            out[nombre] = {"ensamble": "FALLO"}
            continue
        out[nombre] = {
            "mb_bytes": dst.stat().st_size,
            "respuestas": {f"{b:02x}": {"E1": run(rc.ENGINE_A, dst, bytes([b])),
                                         "E2": run(rc.ENGINE_B, dst, bytes([b]))}
                           for b in (0x00, 0x01, 0x02, 0x30, 0x31)},
            "EOF_stdin_vacio": {"E1": run(rc.ENGINE_A, dst, b""),
                                "E2": run(rc.ENGINE_B, dst, b"")},
        }
    return {"sonda": "receivers", "pregunta": "que hace el receptor con cada byte y con EOF",
            "casos": out}


def probe_ascii() -> dict:
    """El alfabeto real del artefacto sellado de G2: se delega en el harness sellado.

    El informe se escribe a un archivo del directorio temporal para no mezclar dos JSON en
    stdout; aqui solo se devuelve el hex crudo que cada interprete observo por caso.
    """
    informe = Path(tmp.name) / "sellado_bounce.json"
    rc_main = rc.main(["run_classic.py", "--kind", "bounce", "--max-steps", "2000000",
                       "-o", str(informe)])
    data = json.loads(informe.read_text(encoding="utf-8"))
    return {"sonda": "ascii", "pregunta": "que bytes imprime el A sellado de G2",
            "rc_informe": rc_main, "todo_pass": data["todo_pass"],
            "artefacto": data["artefacto"], "artefacto_sha256": data["artefacto_sha256"],
            "stdout_crudo_por_caso": {
                c["opcode"]: {"esperado_host": c["esperado_host"],
                              "E1_hex": c["A"]["stdout_raw_hex"],
                              "E1_salida_latin1_hex": c["A"]["salida"].encode("latin-1").hex(),
                              "E2_hex": c["B"]["stdout_raw_hex"],
                              "modelo_C_hex": c["C"]["stdout_raw_hex"],
                              "pasos": c["A"]["pasos"], "veredicto": c["veredicto"]}
                for c in data["casos"]}}


def main(argv):
    mode = argv[1] if len(argv) > 1 else "markers"
    if mode not in ("markers", "receivers", "ascii"):
        print(f"modo desconocido: {mode}", file=sys.stderr)
        return 2
    if not LMAO.is_file():
        print(f"no existe el ensamblador: {LMAO}", file=sys.stderr)
        return 2
    global tmp
    tmp = tempfile.TemporaryDirectory(prefix="g3probe_")
    try:
        if mode == "markers":
            res = probe_markers()
        elif mode == "receivers":
            res = probe_receivers()
        else:
            res = probe_ascii()
    finally:
        shutil.rmtree(tmp.name, ignore_errors=True)
    res["herramientas"] = {"lmao": str(LMAO), "generador_upstream": str(GEN),
                           "upstream_sha256": rc.sha256(GEN)}
    res["interpretes"] = {"E1": str(rc.ENGINE_A), "E2": str(rc.ENGINE_B)}
    sys.stdout.write(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
