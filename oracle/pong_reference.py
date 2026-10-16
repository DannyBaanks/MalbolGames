#!/usr/bin/env python3
"""MALGAMES/PONG_V0 reference oracle — contrato `pong1`.

Oraculo de referencia: jamas participa de la corrida computacional de una VM. Genera y verifica
expectativas de estado y de frame; la fisica y el render viven aqui unicamente como especificacion
independiente contra la que se compara la salida de Malbolge.

    pong_reference.py step     < 'pong1;<11>;<lm>,<rm>'  > 'pong1;<11>\n'
    pong_reference.py chain    < 'pong1;<11>' + N lineas de trabajo  > N lineas de estado
                                 (cada linea de trabajo debe llevar el estado actual; si no
                                  coincide, se rechaza: el encadenamiento no es tolerante)
    pong_reference.py render   < 'pong1;<11>'               > bytes del frame ASCII
    pong_reference.py selftest                               > resumen; exit 0 si todo pasa

Salida: LF exclusivo, sin CR y sin BOM (docs/PONG_MIN_SPEC.md par. 3). Entrada invalida: mensaje en
stderr, exit != 0 y CERO bytes en stdout.
"""
import sys

SPEC = "pong1"
NSTATE = 11
MAX_TICK = 2**31 - 1
MAX_SCORE = 99


class BadInput(Exception):
    pass


def _canon_int(f: str) -> int:
    if f == "" or f == "-":
        raise BadInput(f"entero vacio o suelto: {f!r}")
    body = f[1:] if f[0] == "-" else f
    if not body.isdigit() or (len(body) > 1 and body[0] == "0"):
        raise BadInput(f"no es decimal con signo canonico: {f!r}")
    if f == "-0":
        raise BadInput("-0 no es canonico")
    return int(f)


def parse_state(line: str):
    """`pong1;W,H,bx,by,vx,vy,pl,pr,sl,sr,t` -> 11 enteros validados contra el contrato."""
    parts = line.rstrip("\n").split(";")
    if len(parts) != 2 or parts[0] != SPEC:
        raise BadInput(f"prefijo o separadores invalidos: {line!r}")
    fields = parts[1].split(",")
    if len(fields) != NSTATE:
        raise BadInput(f"se esperaban {NSTATE} campos, hay {len(fields)}: {parts[1]!r}")
    v = [_canon_int(f) for f in fields]
    w, h, bx, by, vx, vy, pl, pr, sl, sr, t = v
    if not 2 <= w <= 64 or not 2 <= h <= 64:
        raise BadInput(f"tablero fuera de 2..64: {w}x{h}")
    if not 0 <= bx <= w - 1 or not 0 <= by <= h - 1:
        raise BadInput(f"pelota fuera de tablero: ({bx},{by}) en {w}x{h}")
    if vx not in (-1, 1) or vy not in (-1, 1):
        raise BadInput(f"velocidades deben ser -1 o +1: {vx},{vy}")
    if not 0 <= pl <= h - 1 or not 0 <= pr <= h - 1:
        raise BadInput(f"paleta fuera de filas: {pl},{pr} en h={h}")
    if not 0 <= sl <= MAX_SCORE or not 0 <= sr <= MAX_SCORE:
        raise BadInput(f"marcador fuera de 0..{MAX_SCORE}: {sl},{sr}")
    if not 0 <= t <= MAX_TICK:
        raise BadInput(f"tick_index fuera de 0..2^31-1: {t}")
    return tuple(v)


def parse_work(line: str):
    """`pong1;<11>;<lm>,<rm>` -> (estado, left_move, right_move)."""
    parts = line.rstrip("\n").split(";")
    if len(parts) != 3 or parts[0] != SPEC:
        raise BadInput(f"linea de trabajo debe ser {SPEC};<11>;<lm>,<rm>: {line!r}")
    moves = parts[2].split(",")
    if len(moves) != 2:
        raise BadInput(f"se esperaban 2 movimientos: {parts[2]!r}")
    lm, rm = (_canon_int(m) for m in moves)
    for name, m in (("left_move", lm), ("right_move", rm)):
        if m not in (-1, 0, 1):
            raise BadInput(f"{name} debe ser -1, 0 o +1: {m}")
    return parse_state(f"{SPEC};{parts[1]}"), lm, rm


def clamp(x: int, lo: int, hi: int) -> int:
    return lo if x < lo else hi if x > hi else x


def fmt(state) -> str:
    return f"{SPEC};" + ",".join(str(x) for x in state) + "\n"


def step(state, left_move: int, right_move: int):
    """docs/PONG_MIN_SPEC.md par. 4 — orden total: tick, paletas, eje vertical, eje horizontal."""
    w, h, bx, by, vx, vy, pl, pr, sl, sr, t = state
    if t + 1 > MAX_TICK:
        raise BadInput(f"tick_index desbordaria 2^31-1: {t} -> {t + 1}")
    t += 1
    pl = clamp(pl + left_move, 0, h - 1)
    pr = clamp(pr + right_move, 0, h - 1)
    ny = by + vy
    if ny < 0 or ny > h - 1:
        vy = -vy
        ny = by + vy
    by = ny
    nx = bx + vx
    if nx < 0:
        if pl == by:
            return (w, h, 0, by, 1, vy, pl, pr, sl, sr, t)
        return (w, h, w // 2, h // 2, 1, -1, pl, pr, sl, min(sr + 1, MAX_SCORE), t)
    if nx > w - 1:
        if pr == by:
            return (w, h, w - 1, by, -1, vy, pl, pr, sl, sr, t)
        return (w, h, w // 2, h // 2, -1, -1, pl, pr, min(sl + 1, MAX_SCORE), sr, t)
    return (w, h, nx, by, vx, vy, pl, pr, sl, sr, t)


def render(state) -> str:
    """docs/PONG_MIN_SPEC.md par. 5 — puntos, luego paletas, luego pelota. Sin marcador ni tick."""
    w, h, bx, by, _vx, _vy, pl, pr, _sl, _sr, _t = state
    grid = [["."] * w for _ in range(h)]
    grid[pl][0] = "|"
    grid[pr][w - 1] = "|"
    grid[by][bx] = "o"
    return "".join("".join(row) + "\n" for row in grid)


REJECHABLES = [
    "pong2;8,4,0,0,1,1,0,0,0,0,0",
    "pong1;1,1,0,0,1,1,0,0,0,0,0",
    "pong1;8,4,9,0,1,1,0,0,0,0,0",
    "pong1;8,4,0,0,0,1,0,0,0,0,0",
    "pong1;8,4,0,0,1,1,0,0,0,0,0,2147483648",
    "pong1;8,4,0,0,1,1,0,0,0,100,0",
    "pong1;8,4,0,0,1,1,0,0,0,0",
    "pong1;08,4,0,0,1,1,0,0,0,0,0",
    "pong1;-0,4,0,0,1,1,0,0,0,0,0",
    "pong1;8,4,0,0,1,1,0,0,0,0,0;2,0",
    "pong1;8,4,0,0,1,1,0,0,0,0,0;0",
    "pong1;8,4,0,0,1,1,0,0,0,0,0,0;0",
]


def selftest() -> int:
    casos = [
        ("E1 horizontal sin colision", (8, 4, 4, 2, 1, -1, 0, 0, 0, 0, 0), (0, 0),
         (8, 4, 5, 1, 1, -1, 0, 0, 0, 0, 1)),
        ("E2 vertical -1->+1 en tope", (8, 4, 4, 0, 1, -1, 0, 0, 0, 0, 0), (0, 0),
         (8, 4, 5, 1, 1, 1, 0, 0, 0, 0, 1)),
        ("E3 rebote en suelo", (8, 4, 4, 3, 1, 1, 0, 0, 0, 0, 0), (0, 0),
         (8, 4, 5, 2, 1, -1, 0, 0, 0, 0, 1)),
        ("E4 golpe de paleta", (8, 4, 0, 2, -1, 1, 3, 0, 0, 0, 0), (0, 0),
         (8, 4, 0, 3, 1, 1, 3, 0, 0, 0, 1)),
        ("E5 gol derecho + reset", (8, 4, 0, 1, -1, 1, 3, 0, 0, 0, 0), (0, 0),
         (8, 4, 4, 2, 1, -1, 3, 0, 0, 1, 1)),
        ("E4b paleta derecha golpe", (8, 4, 7, 1, 1, 1, 0, 2, 0, 0, 0), (0, 0),
         (8, 4, 7, 2, -1, 1, 0, 2, 0, 0, 1)),
        ("E5b gol izquierdo + reset", (8, 4, 7, 1, 1, 1, 0, 0, 0, 0, 0), (0, 0),
         (8, 4, 4, 2, -1, -1, 0, 0, 1, 0, 1)),
        ("E8a marcador 99 saturado", (8, 4, 7, 3, 1, 1, 0, 0, 99, 0, 0), (0, 0),
         (8, 4, 4, 2, -1, -1, 0, 0, 99, 0, 1)),
        ("E0 la paleta se mueve antes que la pelota y convierte un gol en golpe",
         (8, 4, 0, 1, -1, -1, 1, 0, 0, 0, 0), (-1, 0),
         (8, 4, 0, 0, 1, -1, 0, 0, 0, 0, 1)),
        ("E9 paleta fuera de rango se clampa", (8, 4, 4, 2, 1, -1, 0, 3, 0, 0, 0), (-1, 1),
         (8, 4, 5, 1, 1, -1, 0, 3, 0, 0, 1)),
        ("E10 rebote vertical y golpe de paleta en el mismo tick",
         (8, 4, 0, 0, -1, -1, 2, 0, 0, 0, 0), (-1, 0),
         (8, 4, 0, 1, 1, 1, 1, 0, 0, 0, 1)),
    ]
    fallos = 0
    for nombre, s, mv, want in casos:
        got = step(s, *mv)
        if got != want:
            fallos += 1
            print(f"FAIL {nombre}: {got} != {want}", file=sys.stderr)
    frame_want = "|.......\n........\n..o.....\n.......|\n"
    got = render((8, 4, 2, 2, 1, -1, 0, 3, 1, 2, 5))
    if got != frame_want:
        fallos += 1
        print(f"FAIL render: {got!r} != {frame_want!r}", file=sys.stderr)
    pelota_sobre_paleta = render((8, 4, 0, 0, 1, 1, 0, 3, 0, 0, 0))
    if not pelota_sobre_paleta.startswith("o"):
        fallos += 1
        print(f"FAIL prioridad pelota: {pelota_sobre_paleta!r}", file=sys.stderr)
    for malo in REJECHABLES:
        try:
            if malo.count(";") == 2:
                parse_work(malo)
            else:
                parse_state(malo)
            rechazado = False
        except BadInput:
            rechazado = True
        if not rechazado:
            fallos += 1
            print(f"FAIL validacion acepto: {malo!r}", file=sys.stderr)
    print(f"selftest: {len(casos)} transiciones, 2 renders, {len(REJECHABLES)} rechazos -> "
          f"{'PASS' if fallos == 0 else str(fallos) + ' FALLOS'}")
    return 0 if fallos == 0 else 1


def run(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode == "selftest":
        return selftest()
    lines = [l for l in sys.stdin.read().split("\n") if l != ""]
    if not lines:
        print("entrada invalida: entrada vacia", file=sys.stderr)
        return 2
    out = []
    try:
        if mode == "step":
            if len(lines) != 1:
                raise BadInput(f"'step' admite 1 linea, hay {len(lines)}")
            s, lm, rm = parse_work(lines[0])
            out.append(fmt(step(s, lm, rm)))
        elif mode == "chain":
            if len(lines) < 2:
                raise BadInput("'chain' exige 1 linea de estado y al menos 1 de trabajo")
            state = parse_state(lines[0])
            for line in lines[1:]:
                s, lm, rm = parse_work(line)
                if s != state:
                    raise BadInput("la linea de trabajo no continua el estado actual")
                state = step(state, lm, rm)
                out.append(fmt(state))
        elif mode == "render":
            if len(lines) != 1:
                raise BadInput(f"'render' admite 1 linea, hay {len(lines)}")
            out.append(render(parse_state(lines[0])))
        else:
            print(f"modo desconocido: {mode!r} (step|chain|render|selftest)", file=sys.stderr)
            return 2
    except BadInput as e:
        print(f"entrada invalida: {e}", file=sys.stderr)
        return 2
    sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv))
