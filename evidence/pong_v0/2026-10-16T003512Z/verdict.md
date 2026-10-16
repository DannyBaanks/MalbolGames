# Veredicto — intento de encadenar `bounce`→`contact` dentro de un solo programa Malbolge

Corrida `2026-10-16T003512Z` · workspace `MALGAMES` · encargo
`composes/COMPOSE_MALGAMES_PONG_V0.md` · solicitado como «con este nuevo enfoque crees que
ahora si podriamos intentar algo como malpong … si intentemos eso».

## Pregunta y respuesta

**¿Se puede encadenar el rebote vertical y la puerta de gol en UN solo programa, haciendo que
la VM derive la fila post-vertical en vez de recibirla pre-codificada por ruta de despacho?**

**No con el kernel que existe hoy, y la causa no es el tamaño.** La idea era correcta en su
parte económica: el despacho N-way cuesta ~1 100–1 300 B por ruta (techo medido: 24 rutas
ensamblan, 32 no), así que expresar la transición como *dataflow* sobre el kernel MBIR sellado
(`alu_rel_pass25.mb`, 57 511 B, 25/25) haría el costo independiente del producto
(by, vy, pl). Se probó. Lo que falla es la **capacidad medida del kernel**: su `CMP_EQ` no es
una igualdad y su aritmética solo sabe imprimir cinco valores.

## Control previo que legitima todo lo demás

Antes de afirmar nada sobre el kernel se descartó la explicación barata —que MALGAMES lea mal
la ISA— reproduciendo **los 25 vectores de `ALU_REL_STATUS.md` tal cual** en los tres
intérpretes, con control doble: salida *y* número de pasos.

**25/25 `FIEL_A_EVIDENCIA_SELLADA`**, 0 desacuerdos, pasos 58 689 – 83 478 idénticos a la
tabla documentada (`raw/replay_alu_rel.json`). El harness es exacto. Por tanto lo que sigue es
propiedad del kernel, no del observador.

## Qué se midió

| # | Afirmación | Estado | Sostén |
|---|---|---|---|
| 1 | El harness de MALGAMES reproduce bit-a-bit el corpus sellado de ALU_REL (salida y pasos) | **DEMOSTRADO** | 25/25, `raw/replay_alu_rel.json` |
| 2 | `CMP_EQ` del kernel es la igualdad sobre el dominio del tick (0..3) | **FALSO** | rejilla 5×5: la diagonal solo acierta en `2 == 2`; `0==0`, `1==1`, `3==3`, `4==4` imprimen `00`; falso positivo en `2==3` y `2==4` (`raw/auditoria_isa_75.json`) |
| 3 | Equivalente empírico de `CMP_EQ` sobre 0..4 × 0..4 | **DEMOSTRADO** (caracterización, no prueba) | `verdadero ⇔ op1 == 2 ∧ op2 ∈ {2,3,4}`; 19/25 aciertos |
| 4 | El vocabulario imprimible del kernel es acotado | **DEMOSTRADO** | solo `{0x00, 0x01, 0x02, 0x05, 0x07}`; el valor **3 del tablero 8×4 no es imprimible** (`raw/06_matrices_operadores.txt`) |
| 5 | `ADD`/`SUB` calculan enteros del dominio | **FALSO** | `ADD` 5/25 (acierta en (1,1),(2,0),(2,3),(3,4),(4,3)); `SUB` 4/25 (solo la franja de los vectores sellados) |
| 6 | La fila post-vertical puede *derivarse* por dataflow en el kernel | **FALSO** | 0/4: el stream de derivación imprime `0xc6` en los cuatro puntos interiores; con tres operaciones encadenadas el valor se pierde |
| 7 | La puerta encadenada reproduce la tabla `contact` sellada | **12/16** | los 4 fallos son **exactamente** los 4 casos donde la puerta debe valer 1; los 12 aciertos son inercia (el kernel imprime `00` para casi todo) |
| 8 | El bloqueo es por celdas/tamaño | **FALSO** | se reutilizó un artefacto ya sellado de 57 511 B; no hubo ensamblado nuevo en ninguna corrida |
| 9 | El mecanismo es clasificación por etiqueta, no aritmética | **DEMOSTRADO** (lectura del HeLL sellado) | 6 etiquetas de resultado (`sum_is_2/5/7`, `diff_is_0/1/2_from_phase2`) materializadas por 5 constantes `ROT` {0, 3, 6, 15, 21}, `raw/07` |
| 10 | `ONE_TICK_NO_COLLISION_VM` · `STATEFUL_MIN_PONG_VM` · `VM_RENDER_8x4` · `FULL_FRAME_VM` · MALPONG | **NOT_DEMONSTRATED** | sin cambio respecto del sellado G2; esta corrida acota por qué el escalón anterior estaba bloqueado |

## Declaración de alcance (Anexo A.5)

Este intento reduce **ALCANCE**, no *encoding*: se limitó el dominio a la franja interior
`by ∈ {1,2}`, porque en los bordes (`by=0, vy=−1` y `by=h−1, vy=+1`) la reflexión invierte el
signo y exige bifurcación condicional, que este kernel no tiene. Se declaró antes de correr y
se respetó: ningún fixture congelado, ni doc upstream, ni el oráculo se tocaron. La reducción
de alcance **no fue suficiente**: el techo aparece también dentro de la franja interior.

## Condición falsable (a): resultado

Pactada: «el `by` derivado debe reproducir las salidas ya selladas (8/8 y 16/16)».

- Verificación **offline** (especificación, sin VM): la fórmula interior `ny = by − 1 + 2e`
  coincide con el oráculo y con la tabla `contact` sellada en los 16 puntos → **16/16**.
- Verificación **en VM**: la derivación de `ny` falla **0/4** y la puerta encadenada queda
  **12/16**. Condición (a): **FALSA**.

Se registra como negativo documentado. No se retocó ninguna expectativa para «hacer pasar» el
caso, y no se cambió ni una constante de los fixtures.

## Condición falsable (b): resultado

Pactada: `lmao` rc=0 y ≤ 56 361 B. **No aplica**: no se ensambló nada, se reutilizó el kernel
sellado. Como el obstáculo apareció antes de cualquier cuestión de tamaño, esta condición no
aporta evidencia en ninguna de las dos direcciones, y así se anota.

## Nomenclatura nueva

`MBIR_ALU_REL_IS_A_CLASSIFIER` — el kernel MBIR «Unified Relational ALU» (`alu_rel_pass25.mb`)
es un **clasificador acotado de operandos** con un vocabulario de salida de cinco valores, no
una ALU. Su corpus 25/25 es fiel y verificable (replay exacto en salida y pasos), pero **no
ejerce la reflexividad `a == a` fuera de `a = 2`**. Toda planificación de MALGAMES que asuma
«ya tengo aritmética en VM» por leer ese 25/25 está leyendo mal la evidencia: el número es
cierto y el alcance es otro.

## Por qué el corpus sellado no ve el defecto

En los cuatro vectores relacionales encadenados de `ALU_REL_STATUS.md` el resultado de la
aritmética previa **siempre acaba valiendo 2** — `(1+1)==2`, `(4−2)==2`, `(2+0)==2` y sus
variantes falsas comparan 2 contra 0/1/1. El dominio realmente ejercitado de `CMP_EQ` es
`op1 == 2`. No es un error de upstream: upstream documenta «Small-operand lookup … the result
byte is ROT 0, 3, 6, 15, or 21» en `M2_ALU_STATUS.md` y lista «Arbitrary Signed arithmetic»
como *no demostrado*. Lo que aporta esta corrida es la **medida del techo**, que antes era
prosa.

## Límites explícitos

- Ninguna corrida usó Malbolge Unshackled/Extrovertido: solo Clásico 3^10.
- Los intérpretes A y B son **el mismo ELF** (sha `3257f1ae…` idéntico). Son tres ejecuciones
  sobre dos implementaciones independientes, más el modelo Python. No se infla a «tres vías
  reales».
- La caracterización `op1 == 2 ∧ op2 ∈ {2,3,4}` es **empírica en 0..4 × 0..4** (25 pares,
  75 casos con las otras dos ops). No se afirma para operandos mayores.
- `0xc6` como salida de la derivación es lo que el kernel imprime, no lo que «quería» imprimir:
  se reporta la observación cruda, sin reinterpretarla.
- MALGAMES no es repositorio git: la cadena de sellado es a 2 vías (worktree == sello).

## Qué abre esto para el siguiente paso

El bloqueo quedó localizado con precisión, así que el siguiente escalón tiene dos rutas
disjuntas y ambas declarables:

1. **Kernel con igualdad real** (`CMP_EQ` reflexivo sobre 0..3, o `CMP_LT`/`CMP_GT`
   multiplexados). Es trabajo de `MALBOLGE-MB-DATABASE`, con 1 538 celdas de margen: no es
   gratis ni evidente.
2. **Autoría HeLL directa** (estilo `example_adder.hell`: bucles por estado de ciclo xlat2,
   55 725 B funcionando), que es la vía con la que se demostró `CMP_LT` fuera del generador.
   Permite un programa que lea la codificación y calcule, en vez de despachar por tabla.

Ninguna de las dos la ejecuta esta corrida; se deja como siguiente paso, no como claim.

## Reproducir

```bash
cd "ISyCo Git/MALGAMES/vm/nested"
python3 replay_alu_rel.py run          # ~4 min   -> 25/25 FIEL_A_EVIDENCIA_SELLADA, rc 0
python3 audit_alu_rel_isa.py run       # ~6 min   -> rejilla 75, desacuerdos 0
python3 pong_nested.py run             # ~2.5 min -> rc 1 (12/16): el negativo es el resultado
python3 matriz_operadores.py <informe.json>
python3 extracta_estructura_kernel.py
```

Todo aborta si el SHA-256 del kernel copia (`3b6c011b…`) no coincide con el sellado. Upstream
queda en `d479473` con 0 archivos modificados.
