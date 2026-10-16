#!/usr/bin/env python3
"""trit_mask_probe.py — ¿es expresable un CAMPO/mascara de trits en Malbolge Clasico?

Por que existe este probe
------------------------
El despacho N-way de `mbir_dispatch_gen.py` cuesta ~1 170 B por ruta (el discriminador
decrementa hasta underflow). Encadenar `bounce` -> `contact` por enumeracion pide
(by, vy, pl) = 4 x 2 x 4 = 32 rutas -> ~65.7 KB contra 59 049 celdas: NO ensambla
(medido en evidence/pong_v0/2026-10-15T203244Z/raw/08_escalado_despacho.txt).

La alternativa es no enumerar el producto: empaquetar los campos en trits SEPARADOS de
UN byte (by=t0,t1 pl=t2,t3 vy=t4; max 201 < 256) y, dentro de la VM, **anular los trits
que no interesan y conservar los que si**, para despues discriminar sobre el valor ya
aislado (<= 9 rutas en vez de 32).

La pregunta dura es si esa mascara es alcanzable con las UNICAS primitivas de posición
que la maquina tiene: `crazy` con un registro de control fijo, y `rot`, que desplaza los
trits exactamente UNA posicion. Como rot gira el registro entre aplicaciones, la posicion
p ve los trits de control c[p], c[p-1], ... del MISMO control: las palabras por posicion
son ventanas ciclicas de una sola palabra de 10 trits. Eso es estrictamente mas debil que
la eleccion libre por posicion que midio GUS_TRIT_ALGEBRA_V0, y aqui no estaba medido.

Que afirma este script (y que no)
---------------------------------
- AFIRMA: para L aplicaciones con rot entre ellas, que patrones (KEEP=identidad,
  ZERO=constante) son realizables por algun control de 10 trits, enumerados los 59 049.
- AFIRMA: el coste de la restriccion ciclica, contra el control de eleccion libre.
- NO AFIRMA nada de Pong, de un tick, ni de que el codegen pueda emitir la secuencia:
  es un predicado de expresabilidad del algebra, previo a escribir HeLL.

Orientacion (la trampa T24): crazy(ctrl, cell) = TBL[cell][ctrl]; la tabla se LEE del
oraculo upstream y se verifica contra la tabla sellada del pack. Upstream solo lectura;
al final se re-verifica su SHA-256 y se informa de cualquier cambio.

Salida: LF exclusivo, sin CR, sin BOM. Entrada: ninguna (stdin no se toca).
"""
from __future__ import annotations

import hashlib
import re
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]                                   # MALGAMES/
ORACLE = REPO.parent / "MALBOLGE-MB-DATABASE" / "tools" / "oracle_classic.py"

TRITS = 10
N = 3 ** TRITS
IDMAP = (0, 1, 2)
CONSTS = {c: (c, c, c) for c in range(3)}

# Cross-check target: the sealed table used by GUS_TRIT_ALGEBRA_V0 (row=cell, col=ctrl).
SEALED = ((1, 0, 0), (1, 0, 2), (2, 2, 1))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_table():
    """Read _CRAZY from the upstream oracle; never hand-copy it."""
    if not ORACLE.is_file():
        return None, "ORACLE AUSENTE: %s" % ORACLE
    src = ORACLE.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"_CRAZY\s*=\s*\((.*?)\)\s*\n", src, re.S)
    if not m:
        return None, "_CRAZY no encontrado en el oraculo"
    digits = [int(x) for x in re.findall(r"\d", m.group(1))]
    if len(digits) != 9:
        return None, "_CRAZY tiene %d digitos, se esperaban 9" % len(digits)
    flat = tuple(digits)                      # oracle order: row-major TBL[row][col]
    return (flat[0:3], flat[3:6], flat[6:9]), None


def col_map(TBL, a):
    """The per-trit map induced by a control trit a (the cell value varies)."""
    return (TBL[0][a], TBL[1][a], TBL[2][a])


def compose(seq):
    """Apply maps in order seq[0] first. Returns the induced map on {0,1,2}."""
    m = IDMAP
    for f in seq:
        m = (f[m[0]], f[m[1]], f[m[2]])
    return m


def words_by_semantics(fmaps, maxL):
    """For each length L, which map each control-word induces."""
    out = {}
    for L in range(1, maxL + 1):
        d = {}
        for w in product(range(3), repeat=L):
            d[w] = compose([fmaps[a] for a in w])
        out[L] = d
    return out


def cyclic_windows(TBL, fmaps, L):
    """For every control word c (59 049), the induced map at each original position.

    Convention A (register rotated before each use): at step j the register index k
    holds the original trit p = k + j, and the control trit applied is c[k] = c[(p-j) % 10].
    So the word seen by original position p is (c[p], c[p-1], ..., c[p-L+1]).
    Convention B is the mirror: (c[p], c[p+1], ..., c[p+L-1]).
    """
    res = {}
    for c_int in range(N):
        c = [(c_int // 3 ** i) % 3 for i in range(TRITS)]
        A, Bv = [], []
        for p in range(TRITS):
            wa = tuple(c[(p - j) % TRITS] for j in range(L))
            wb = tuple(c[(p + j) % TRITS] for j in range(L))
            A.append(compose([fmaps[a] for a in wa]))
            Bv.append(compose([fmaps[a] for a in wb]))
        res[c_int] = (A, Bv)
    return res


def classify(patterns, TBL, fmaps, L, field_sets):
    """Which (KEEP,ZERO) targets are hit by some cyclic control, per convention."""
    wins = cyclic_windows(TBL, fmaps, L)
    hit = {"A": set(), "B": set()}
    example = {}
    for c_int, (A, Bv) in wins.items():
        for conv, maps in (("A", A), ("B", Bv)):
            ident = tuple(p for p in range(TRITS) if maps[p] == IDMAP)
            const = tuple(p for p in range(TRITS) if maps[p] in CONSTS.values())
            hit[conv].add((ident, const))
            key = (conv, ident, const)
            example.setdefault(key, c_int)
    want = []
    for keep in field_sets:
        rest = tuple(p for p in range(TRITS) if p not in keep)
        for conv in ("A", "B"):
            # exact: identity precisely on `keep`, constant on all of `rest`
            ok = (keep, rest) in hit[conv] or any(
                (k, z) == (keep, rest) for (k, z) in hit[conv]
            )
            # also accept supersets: extra positions left untouched but irrelevant
            sup = any(k == keep and set(rest) <= set(z) for (k, z) in hit[conv])
            want.append((conv, keep, ok, sup,
                         example.get((conv, keep, rest))))
    return want


def free_choice_control(fmaps, maxL):
    """Control: with FREE per-position word choice, is (identity here, constant there)
    reachable at all? Yes iff identity and some constant are each reachable words."""
    ident_L = const_L = None
    for L in range(1, maxL + 1):
        ws = words_by_semantics(fmaps, L)[L]
        maps = set(ws.values())
        if ident_L is None and IDMAP in maps:
            ident_L = L
        if const_L is None and any(m in CONSTS.values() for m in maps):
            const_L = L
        if ident_L and const_L:
            break
    return ident_L, const_L


def p(*a):
    print(*a)


def main():
    p("trit_mask_probe — MALGAMES/G2 pre-check (expresabilidad de mascara de trits)")
    p("upstream Oracle: %s" % ORACLE)
    sha_before = sha256(ORACLE) if ORACLE.is_file() else "AUSENTE"
    p("sha256(oracle_classic.py) ANTES = %s" % sha_before)

    TBL, err = load_table()
    if err:
        p("FALLO DE ORIGEN: %s" % err)
        return 2
    p("tabla leida del oraculo (row=cell, col=ctrl) = %s" % (TBL,))
    p("coincide con la tabla sellada de GUS_TRIT_ALGEBRA_V0 = %s"
      % (TBL == SEALED,))
    if TBL != SEALED:
        p("FALLO: el oraculo y el pack no concuerdan; no seguir.")
        return 2

    fmaps = {a: col_map(TBL, a) for a in range(3)}
    p("mapas de columna f_a = " + "  ".join("f%d=%s" % (a, fmaps[a]) for a in range(3)))

    MAXL = 6
    ident_L, const_L = free_choice_control(fmaps, MAXL)
    p("")
    p("CONTROL (elegencia libre por posicion, el resultado del pack):")
    p("  longitud minima de palabra para IDENTIDAD  = %s" % ident_L)
    p("  longitud minima de palabra para CONSTANTE   = %s" % const_L)
    words = words_by_semantics(fmaps, MAXL)
    for L in range(1, MAXL + 1):
        ms = set(words[L].values())
        p("  L=%d : %d mapas distintos; identidad=%s; constantes=%s"
          % (L, len(ms), IDMAP in ms,
             sorted(c for c in CONSTS.values() if c in ms)))

    # the field layouts a packed byte would use
    field_sets = [(0, 1), (2, 3), (4,), (0, 1, 2, 3)]
    p("")
    p("MASCARAS CICLICAS (un solo control de 10 trits, rot de 1 entre aplicaciones)")
    p("conv A: word(p) = (c[p], c[p-1], ...);  conv B: word(p) = (c[p], c[p+1], ...)")
    p("KEEP = trits con identidad exacta; ZERO = trits anulados a una constante")
    any_hit = False
    for L in range(1, MAXL + 1):
        res = classify(None, TBL, fmaps, L, field_sets)
        for conv, keep, ok, sup, ex in res:
            p("  L=%d conv=%s keep=%s  exacta=%s  (superset admitido=%s)  control=%s%s"
              % (L, conv, keep, ok, sup,
                 "NINGUNO" if ex is None else "%d (c=%s)" % (
                     ex, [(ex // 3 ** i) % 3 for i in range(TRITS)]),
                 "" if ok else ""))
            if ok:
                any_hit = True
    p("")
    p("VEREDICTO DE EXPRESABILIDAD: %s"
      % ("HAY al menos una mascara de campo exacta con control fijo + rot"
         if any_hit else
         "NO HAY mascara de campo exacta para ningun control fijo con L<=%d: "
         "la restriccion ciclica mata la idea de empaquetar campos en trits" % MAXL))

    sha_after = sha256(ORACLE) if ORACLE.is_file() else "AUSENTE"
    p("")
    p("sha256(oracle_classic.py) DESPUES = %s   (sin mutacion: %s)"
      % (sha_after, sha_after == sha_before))
    return 0 if any_hit else 1


if __name__ == "__main__":
    sys.exit(main())
