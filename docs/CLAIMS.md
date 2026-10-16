# Claims — MalbolGames / PONG_V0

Marca visible: **MalbolGames**. Workspace en disco: `ISyCo Git/MALGAMES` (nombre histórico, citado
por 32 archivos de evidencia sellada; moverlo rompería la cadena de SHA-256). Ver
`docs/PROVENANCE.md` y el README.

Regla de este repo: **ningún claim se enuncia sin decir qué VM lo sostuvo, qué cálculo lo produjo
y qué prueba independiente lo corrobora.** Si falta uno de los tres, el claim va a
`NOT_DEMONSTRADO`.

## Tabla

| claim | estado | quién calcula `S_t → S_{t+1}` | qué lo sostiene | qué NO afirma |
|---|---|---|---|---|
| `ORACLE_ONLY` | **DEMONSTRADO** (2026-10-15) | **CPU del host**, ejecutando dos oráculos escritos a mano | `evidence/pong_v0/2026-10-15T194755Z/`: 31/31 verificaciones, byte-identicas entre Python 3.12 y C11/gcc 13.3; fixtures derivados a mano del contrato; T1–T6 en `tests/test_oracle.py` | Nada sobre Malbolge. Nada sobre rendimiento. No es un juego corriendo. |
| `CONTRATO_PONG1_CONGELADO` | **DEMONSTRADO** (definición, no ejecución) | — | `docs/PONG_MIN_SPEC.md`: orden total, serialización canónica, saturación sin envoltura, render separable, fallo cerrado | Que el contrato sea realizable en Malbolge |
| `MAQUINA_CLASICA_DISPONIBLE` | **DEMONSTRADO** | — (es hecho de inventario) | `evidence/pong_v0/2026-10-15T195127Z/`: dos ELF Linux ejecutan `hello.mal`; `truth_machine.mal` ramifica sobre stdin (136 pasos HALTED); `lt_pass12.mb` reproducido a 81 977 pasos con SHA exacta | Que una VM calcule algo del estado `pong1` |
| `ONE_PREDICATE_FINITE_DOMAIN_CLASSIC_VM` | **DEMONSTRADO** (2026-10-15) | **la VM Malbolge Clásica**, sobre un dominio finito codificado por el host | `evidence/pong_v0/2026-10-15T203244Z/`: `bounce_vertical` 8/8 y `contact_gate` 16/16 con salida y pasos idénticos en 3 intérpretes Clásicos (2 ELF + modelo Python); control de selectividad de ruta con mutante; tabla derivada del spec y contrastada contra el oráculo | Que se calcule aritmética de dominio variable. Que sea un tick, un estado o un frame. Que la VM derive la codificación estado→byte. |
| `ONE_TICK_NO_COLLISION_VM` | **NOT_DEMONSTRADO** | nadie todavía | — | — |
| `STATEFUL_MIN_PONG_VM` | **NOT_DEMONSTRADO** | nadie todavía | — | — |
| `VM_RENDER_8x4` | **NOT_DEMONSTRADO** | nadie todavía | — | — |
| `FULL_FRAME_VM` / `DELTA_FRAME_VM` | **NOT_DEMONSTRADO** | nadie todavía | — | — |
| `JUEGO_FUNCIONANDO` | **PROHIBIDO Y NO DEMOSTRADO** | — | — | Está prohibido enunciarlo por el Compose hasta que la transición se calcule dentro de la VM |

## Vocabulario de rutas

`DIRECT_VM` = un programa Malbolge lee la línea de trabajo y emite el siguiente estado.
`NESTED_VM` = un intérprete Malbolge dentro de otro.
Hoy **ninguna** de las dos existe para `pong1`. `HOST_COMPUTED` en cualquier resultado futuro
retira el claim de forma inmediata.

## Prespuesto medido, no supuesto

Una imagen de **un solo kernel** MBIR ocupa 57 511 de 59 049 celdas (margen 1 538). La línea de
trabajo `pong1` son 33 caracteres ASCII y 11 campos. Por tanto `DIRECT_VM` sobre `pong1` completo
está **bloqueado por capacidad y codegen**, no por falta de intérprete. Cualquier avance debe
reducir el *encoding* (operandos de un dígito) o el *alcance* (un predicado), y decir cuál.

## Anexo — corrida G2 `2026-10-15T203244Z` (append, no reescribe lo de arriba)

**El claim nuevo no reduce el *encoding*, reduce el *alcance*.** El Compose pedía decir cuál de
los dos se reducía; se redujo el alcance: en vez de la línea `pong1` de 33 caracteres y 11
campos, un entero pequeño ya codificado por el host. La serialización canónica sigue sin
parsearse dentro de la VM, y eso es exactamente lo que `HOST_COMPUTED` prohibía afirmar: por
eso el claim se llama `ONE_PREDICATE_FINITE_DOMAIN_CLASSIC_VM` y no `ONE_TICK_…`.

Techo de capacidad **medido** para un despacho N-way ensamblado a Clásico (59 049 celdas):

| rutas | `.mb` | margen | ensamblado |
|---|---|---|---|
| 8 | 35 515 | 23 534 | rc=0 |
| 16 | 45 949 | 13 100 | rc=0 |
| 20 | 51 683 | 7 366 | rc=0 |
| 24 | 56 361 | 2 688 | rc=0 |
| 32 | — | — | **rc=1**, `Free space exceeded (Add Malbolge command)` |

Crecimiento ≈ 1 180 celdas por ruta. Consecuencia: un **despacho** cabe holgadamente; el muro
de `DIRECT_VM` sigue siendo el kernel MBIR de 57 511 celdas, no el despacho. Los dos
predicados de esta corrida caben porque son clasificadores por valor, no un kernel aritmético.

Vocabulario añadido: `ONE_PREDICATE_FINITE_DOMAIN_CLASSIC_VM` requiere decir (a) el dominio
finito exacto, (b) la codificación estado→byte y quién la hizo, (c) la tabla de verdad y de
dónde se derivó, (d) qué intérpretes la ejecutaron. Sin esas cuatro líneas el enunciado no es
usable.

## Anexo — corrida `2026-10-16T003512Z` (append, no reescribe lo de arriba)

**Esta corrida no añade un positivo: añade un negativo medido y el techo de una pieza ajena.**
Ninguna fila de la tabla de arriba cambia de estado.

| claim nuevo | estado | quién calcula | qué lo sostiene | qué NO afirma |
|---|---|---|---|---|
| `HARNESS_FIEL_A_CORPUS_UPSTREAM` | **DEMOSTRADO** | el harness de MALGAMES + la VM Clásica | `raw/replay_alu_rel.json`: los **25** vectores sellados de `ALU_REL_STATUS.md`, transcritos tal cual, reproducidos con control doble (salida hex **y** número de pasos, 58 689–83 478), 0 desacuerdos entre intérpretes | Que MALGAMES sepa hacer aritmética. Solo legitima que la lectura de la ISA es exacta, y por tanto que el negativo de abajo es propiedad del kernel y no del observador. |
| `TICK_CHAIN_SINGLE_PROGRAM_VM` | **NEGATIVA MEDIDA** (condición falsable (a) **FALSA**) | nadie: la VM no deriva la fila post-vertical | `run.json.condiciones_falsables_pactadas`: derivación de `ny` **0/4** (imprime `0xc6`), puerta encadenada **12/16** y los 4 fallos son **exactamente** los 4 casos donde la puerta debe valer 1 | Que esté bloqueado por tamaño. La condición (b) **no aplicó**: no se ensambló nada nuevo. |
| `MBIR_ALU_REL_IS_A_CLASSIFIER` | **DEMOSTRADO** (techo medido sobre 0..4 × 0..4) | — (es propiedad de un artefacto) | rejilla de 75 casos (`raw/auditoria_isa_75.json`): `CMP_EQ` verdadero solo en `{(2,2),(2,3),(2,4)}` ⇔ `op1 == 2 ∧ op2 ∈ {2,3,4}`; `ADD` 5/25 y `SUB` 4/25; vocabulario imprimible `{0x00,0x01,0x02,0x05,0x07}`; lectura del HeLL sellado: 6 etiquetas de resultado materializadas por 5 constantes ROT `{0,3,6,15,21}` (`raw/07`) | Que el kernel sea «malo»: su corpus 25/25 es fiel. Que la caracterización valga para operandos > 4. Que upstream esté equivocado: `M2_ALU_STATUS.md` ya dice *Small-operand lookup* y lista *Arbitrary Signed* como no demostrado. |

### Efecto sobre el vocabulario de rutas

`DIRECT_VM` sigue sin existir para `pong1`, y ahora se puede decir **por qué** con una medida en
vez de con una intuición: el obstáculo declarado en «Prespuesto medido» era *capacidad y codegen*;
la corrida de 2026-10-16 lo acota a **capacidad medida del kernel** (reflexividad de `CMP_EQ` y
vocabulario imprimible de 5 valores), con el despacho ya descartado como muro (24 rutas caben).

### Nomenclatura

`NEGATIVA MEDIDA` se añade a la tabla como estado propio: es un resultado con entorno, comando,
salida cruda, pasos y hash — no la ausencia de resultado. Un `NOT_DEMONSTRADO` dice «no sé»; una
`NEGATIVA MEDIDA` dice «probé la hipótesis en estas condiciones y era falsa». Confundirlos borra
información de presupuesto para el siguiente paso.

### Lo que sigue bloqueado, dicho con la causa encima

`ONE_TICK_NO_COLLISION_VM` · `STATEFUL_MIN_PONG_VM` · `VM_RENDER_8x4` · `FULL_FRAME_VM` siguen
`NOT_DEMONSTRADO`. A la lista se suma, como bloque explícito: **cualquier predicado que necesite
igualdad reflexiva sobre un valor ≠ 2**, y **encadenar más de dos operaciones aritméticas
conservando el valor** con el kernel actual.
