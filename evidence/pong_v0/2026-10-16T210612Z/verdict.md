# Veredicto — G3: una arista `A(.mb) → byte → B(.mb)` entre dos VMs Malbolge Clásico

Corrida `2026-10-16T210612Z` · workspace `MALGAMES` · encargo
`composes/COMPOSE_MALGAMES_PONG_V0.md` · solicitada como «vale intentemos tu enfoque»,
después de la pregunta sobre dataflow y física simultánea.

## Pregunta y respuesta

**¿Puede un byte que imprime un intérprete Malbolge Clásico ser el byte que otro intérprete
Malbolge Clásico lee y sobre el que calcula, sin que el host vuelva a codificar nada en medio?**

**Sí.** Dos modos, 8/8 casos cada uno, con siete condiciones pactadas antes de correr todas en
verde. Esto cierra un hueco que estaba abierto en toda la línea de trabajo: MALDOOM registra
`CLASSIC_CROSS_READ_STATE_NOT_DEMONSTRATED`, y el `found:false` de `TICK_INC` era vacío porque
tenía `evaluations: 0`. Nadie había medido antes la lectura a través de dos VMs.

## Lo que NO es esta corrida

La pregunta de origen era tratar las físicas simultáneas como workers de dataflow. Este sello
**no** responde esa pregunta. Responde solo el prerequisito, y por dos razones medidas:

1. **Un dataflow dentro de Malbolge no cabe.** El kernel MBIR del tick ocupa 57 511 de 59 049
   celdas; un despacho de 32 rutas ya no ensambla (`rc=1`, `Error: Free space exceeded`,
   `Cannot generate initialization code for cell 58854`). Un planificador sería un segundo
   kernel.
2. **Dejar la física en Python anula la afirmación.** Sería `HOST_COMPUTED`.

Así que el grafo se usó solo como orquestación y se redujo el objetivo a **exactamente una
arista**, sin planificador, sin reloj, sin colas y sin concurrencia.

## El canal se midió, no se eligió

`MARKERS` del generador solo emite caracteres imprimibles y la gramática HeLL
(`chr [!-&(-\[\]-~ ]`) cubre 0x20–0x7E: ningún byte de control se escribe como literal. Por
tanto un canal ASCII `'0'/'1'` exigiría ≥49 rutas de despacho. Con las capacidades medidas
(24 rutas → 56 361 B con 2 688 de margen; 32 rutas → no ensambla; ajuste ≈ 25 091 + 1 303·rutas)
eso son ≈90 KB: **muerto por medida**, no por opinión.

Quedó entonces un alfabeto de dos bytes. La sonda `raw/03` midió qué expresión HeLL produce un
byte crudo en `OUT`: `ROT (1 << 1)` → `0x01` y `ROT (2 << 1)` / `ROT (0t2 << 1)` → `0x02`. No
funcionan `1` (→`0xe3`), `(1 >> 1)` (→`0xa1`), `C1` (→`0x54`), `C2` (→`0xa8`), `(0t11 << 1)`
(→`0x04`), `(C2!1)` (→`0xc6`), `(1!C2)` (→`0xa8`) — en HeLL `>>`/`<<` son **rotación ternaria**,
no shift de bits. Y `0x00` no puede portar dato: es HALT.

## Qué se demostró

| # | Afirmación | Estado | Sostén |
|---|---|---|---|
| 1 | `HANDOFF_SINGLE_EDGE_CLASSIC_VM` — el byte de salida de una VM Clásico es la entrada de otra y la salida de la segunda depende de ese byte | **DEMOSTRADO** | 8/8 en modo nota y 8/8 en modo eco; C1–C7 verdes; `raw/04`, `raw/05` |
| 2 | El byte viaja por la tubería sin re-codificación del host | **DEMOSTRADO** | C3: `tee` == stdout crudo de A solo == byte esperado (`010a`/`020a`, `310a`/`300a`) |
| 3 | El `0x0A` de framing del runner no entra en el cómputo de B | **DEMOSTRADO** | C5: pasos idénticos entre tubería (byte+LF) y alimentación directa (solo byte) — 30 142/30 934 y 29 477 |
| 4 | B no puede inventar el bit | **DEMOSTRADO** | C6: stdin vacío → ninguna salida de programa (26 660 / 26 923 pasos, HALTED) |
| 5 | La salida de B depende del byte de A y no de una constante horneada | **DEMOSTRADO** | C7 nota: el mutante B-swap invierte los 8 casos con el mismo A y el mismo flujo. C7 eco: B inyectivo en 0x30/0x31 |
| 6 | Acuerdo entre intérpretes en la arista completa | **DEMOSTRADO** | C2 en las 4 parejas {E1,E2}², idénticas en salida y pasos; C4 de A vs el modelo C |
| 7 | El alfabeto de una arista por despacho de valor en Clásico está acotado a ≈0x01..0x19 | **DEMOSTRADO** | techo de despacho medido + sondas, `raw/03`, `raw/10` |
| 8 | Red de ≥2 aristas simultáneas entre ≥3 VMs | **NOT_DEMONSTRATED** | A y B corren en serie dentro de una tubería |
| 9 | `STATEFUL_CROSS_TICK_HANDOFF` — el estado `pong1` de 11 campos viaja y la segunda VM lo continúa | **NOT_DEMONSTRATED** | viaja 1 bit por disparo; la codificación estado→byte es externa |
| 10 | Físicas simultáneas sin colisión mediante workers de dataflow | **NOT_DEMONSTRATED** | sigue abierta; esto es el prerequisito, no la respuesta |
| 11 | `ONE_TICK_NO_COLLISION_VM` / `STATEFUL_MIN_PONG_VM` / `VM_RENDER_8x4` / `FULL_FRAME_VM` | **NOT_DEMONSTRATED** | sin cambio: el techo del kernel MBIR sigue vigente |

## Los dos modos y por qué hacen falta ambos

**Modo nota** — `pong_bounce_raw_v0.mb` → `pong_not_v0.mb`. B discrimina `0x01` contra `0x02`
por **ruta de despacho** y calcula NOT. Es la arista fuerte: el receptor reconoce el símbolo.
Cuesta un programa nuevo (A 34 111 B, B 27 243 B).

**Modo eco** — `pong_bounce_v0.mb` (**el artefacto sellado de G2, sin modificar**) →
`pong_echo_v0.mb`. Aquí no se parchó `MARKERS`, así que el byte entra por el **fallback de eco**
del generador intacto y B lo reimprime. La sonda C7c lo prueba: B-ECO con `0x01` emite `'P'`
(la ruta existe y **no** es la que corrió). Es la arista barata y la que demuestra que el
transporte no depende de mis programas nuevos — pero la afirmación «B reconoce el símbolo» es
**FALSE** en este modo y así se declara (`GN3`).

## Selectividad

| flujo por tubería | B normal | B mutante (swap) |
|---|---|---|
| `010a` (bit 0) | `0` @30 142 | `1` @30 145 |
| `020a` (bit 1) | `1` @30 934 | `0` @30 937 |

8/8 invertidos cambiando solo dos constantes de B. El mutante pesa idénticos 27 243 B.

## Nomenclatura nueva

`HANDOFF_SINGLE_EDGE_CLASSIC_VM` — un byte determinado por el cómputo de un intérprete Malbolge
Clásico llega, a través de una tubería del SO y sin re-codificación del host, al stdin de otro
intérprete Malbolge Clásico, cuya salida depende de ese byte. **No** implica red, ni concurrencia,
ni estado compartido, ni tick, ni frame.

## Límites explícitos

- Una arista, un bit, un disparo, dos procesos.
- Sin formato de mensaje: no hay framing de paquete, ni longitud, ni secuencia, ni reloj.
- Ninguna corrida usó Malbolge Unshackled/Extrovertido: solo Clásico 3^10.
- Los 8 puntos son el dominio completo de `bounce_vertical` sobre 8×4, no un muestreo.
- `E1` y `E2` resultaron ser el mismo ELF (sha `3257f1ae98bc…`); las 4 parejas son 3 ejecuciones
  sobre 2 implementaciones. La vía independiente real es el modelo C.

## Integridad de lo que no se tocó

`sha256sum -c SHA256SUMS.txt` → rc=0, 24/24 OK antes y después. `MALBOLGE-MB-DATABASE` en HEAD
`d479473` con `git status --porcelain` = 0 líneas. Los `.mb` sellados de G2 byte-idénticos.
Nada de esto se editó para hacer pasar la prueba.
