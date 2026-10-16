# Veredicto — G2: codegen extendido y predicados del tick dentro de la VM Clásica

Corrida `2026-10-15T203244Z` · workspace `MALGAMES` · encargo
`composes/COMPOSE_MALGAMES_PONG_V0.md` · solicitado como «puedes extender el codegen para
ver si logra funcionar».

## Pregunta y respuesta

**¿Se puede extender el codegen HeLL→Malbolge Clásico de modo que una pieza del tick de
Pong se calcule realmente dentro de la VM?**

**Sí.** La pieza que bloqueaba no era la VM ni el ensamblador: era que
`mbir_dispatch_gen.py` fija `MARKERS = {0x01:'P', …, 0x11:'I'}` en el módulo y no expone
esa tabla por CLI, así que sus rutas emiten letras y no pueden devolver un predicado.
`vm/classic/pong_codegen.py` sustituye esa tabla en memoria por una derivada del contrato,
y a partir de ahí dos predicados de la transición `pong1` se evalúan dentro de la VM
Clásica y su byte de salida depende del byte que la VM leyó en stdin.

## Qué se demostró

| # | Afirmación | Estado | Sostén |
|---|---|---|---|
| 1 | `bounce_vertical(by,vy)` sobre tablero 8×4 (8 puntos) evaluada en VM Clásica | **DEMOSTRADO** | 8/8 PASS × 3 intérpretes, pasos idénticos, `raw/01` |
| 2 | `contact_gate(pl, by_post_vertical)` sobre tablero 8×4 (16 puntos) evaluada en VM Clásica | **DEMOSTRADO** | 16/16 PASS × 3 intérpretes, `raw/02` |
| 3 | La tabla de marcadores la dicta `docs/PONG_MIN_SPEC.md`, no una transcripción a mano | **DEMOSTRADO** | `pong_codegen.py check` vs oráculo: 8/8 y 16/16, `raw/09` |
| 4 | La extensión es mínima y no muta la herramienta compartida | **DEMOSTRADO** | diff = solo 8 constantes (`raw/07`); `MALBOLGE-MB-DATABASE` en `d479473` con 0 archivos modificados |
| 5 | Un despacho N-way cabe en Clásico hasta ~24 rutas; con 32 no ensambla | **DEMOSTRADO** | capacidad medida con `rc` y `stderr` del ensamblador, `raw/08` |
| 6 | La salida depende del byte leído, no de una constante fija | **DEMOSTRADO** | control de selectividad con mutante, `raw/06` |
| 7 | La aritmética del tick (suma, clamp, envoltura) se calcula en VM | **NOT_DEMONSTRATED** | los programas no suman enteros de dominio variable |
| 8 | `ONE_TICK_NO_COLLISION_VM` | **NOT_DEMONSTRATED** | falta la transición completa y el estado de 11 campos |
| 9 | `STATEFUL_MIN_PONG_VM` / `VM_RENDER_8x4` / `FULL_FRAME_VM` | **NOT_DEMONSTRATED** | los programas son one-shot: leen 1 byte, escriben 1 byte, HALT |
| 10 | El predicado se alimenta del estado `pong1` real sin traducción del host | **NOT_DEMONSTRATED** | la codificación estado→byte es externa a la VM |

## Nomenclatura nueva

`ONE_PREDICATE_FINITE_DOMAIN_CLASSIC_VM` — una función `dominio_finito → {0,1}` de la
transición `pong1` evaluada íntegramente dentro de un intérprete Malbolge Clásico (3^10),
donde el byte emitido está determinado por el byte leído en stdin. **No** implica
aritmética general en VM, ni estado, ni tick, ni frame.

## Hecho del contrato que esta corrida afinó

El eje vertical corre **antes** que el horizontal, así que la puerta de gol compara la
paleta clampeada contra la fila de la pelota **posterior** al rebote. Una primera versión
del check indexó por la fila de entrada y falló 8/16. Al leer la fila post-vertical desde
un estado de pared, los casos de Gol devolvían `by=2` siempre, porque la rama de Gol
reescribe `by` a `h//2`: hubo que derivarla por una vía interior. Se corrigió el check; el
oráculo y el spec no se tocaron. Registrado como `N1`.

## Qué no cambió con respecto al precheck

El precheck (`2026-10-15T195127Z`) ya había determinado que faltaba capacidad/codegen, no
VM. Esta lo confirma y lo acota: el techo de un **despacho** es ~24 rutas; el techo que
bloquea un **tick completo** sigue siendo el kernel MBIR (57 511 de 59 049 celdas). Los 24
predicados de esta corrida caben porque son clasificadores, no un kernel.

## Límites explícitos

- Ninguna corrida aquí usó Malbolge Unshackled/Extrovertido: solo Clásico 3^10.
- Los 24 puntos son el dominio completo de cada predicado sobre 8×4; no son un muestreo.
- Los dos predicados son **independientes entre sí**: no se encadenan, no comparten estado,
  y la VM no deriva `by_post_vertical` — se lo damos codificado.
- MALGAMES no es repositorio git: la cadena de sellado es a 2 vías (worktree == sello), no a
  3 como en MALDOOM. No se afirma una tercera vía que no existe.

## Reproducir

```bash
cd "ISyCo Git/MALGAMES/vm/classic"
python3 pong_codegen.py check --kind bounce
python3 pong_codegen.py check --kind contact
python3 pong_codegen.py emit --kind bounce  -o pong_bounce_v0.hell
python3 pong_codegen.py emit --kind contact -o pong_contact_v0.hell
"../../MALBOLGE-MB-DATABASE/third_party/lmao/bin/lmao" -o pong_bounce_v0.mb  pong_bounce_v0.hell
"../../MALBOLGE-MB-DATABASE/third_party/lmao/bin/lmao" -o pong_contact_v0.mb pong_contact_v0.hell
python3 run_classic.py --kind bounce                  # -> 8/8, exit 0
python3 run_classic.py --kind contact                 # -> 16/16, exit 0
```

## Añadido de la misma corrida — el ensamblador no es byte-determinista

Al intentar reproducir el `.mb` desde el `.hell` apareció un hallazgo propio: **LMAO v0.6.0
emite cola variable**. Mismo fuente, tres ensamblados: tamaño fijo, prefijo común de 34 010 de
34 105 bytes en `bounce` (99,72 %) y 44 882 de 45 109 en `contact` (99,50 %), y una cola de
94–227 bytes con contenido distinto en cada corrida. Dos de tres ensamblados de `bounce` sí
salieron idénticos entre sí, así que no es un fallo estable: depende del estado del proceso.

Lo relevante para el claim: **los cuatro binarios (sellado + 3 reensamblados) producen salidas y
pasos idénticos en los tres intérpretes, en los 8 casos**. La cola es conductualmente inerte. El
programa que ejecuta la VM es el prefijo, y el prefijo sí es determinista.

Consecuencia metodológica, escrita para que nadie pierda tiempo con ella: el artefacto canónico
es el `.mb` byte a byte (sellado en `artifacts/`); un test de regresión sobre
`sha256(lmao(.hell)) == sha sellado` daría **falso negativo**. La regresión válida es
`sha(.hell)` + igualdad de comportamiento. Ningún claim de `raw/01`/`raw/02` depende del
determinismo del ensamblador: se midieron sobre el binario sellado.

Detalle y tabla completa en `raw/11_no_determinismo_lmao.txt`.
