# Veredicto del pre-chequeo G2 — qué máquina hay y dónde está el muro

**Run:** `2026-10-15T195127Z` · Re-verificación:
`cd evidence/pong_v0/2026-10-15T195127Z && LC_ALL=C.UTF-8 sha256sum -c SHA256SUMS.txt`

## Respuesta a la pregunta que abre G2

El Compose pregunta si hay «VM fiable». **Sí la hay, y la verifiqué en vivo yo mismo** — sin
compilar nada, sin escribir fuera de MALGAMES:

* `Malbolge-Engine/malbolge` (ELF Linux) y `reference_interpreter_classic` (ELF Linux) ejecutan
  `hello.mal`; el primero añade un newline de framing (**13** bytes de stdout), el segundo emite
  los **12** exactos.
* Dentro de la VM clásica hay **ramificación sobre stdin**: `truth_machine.mal` con `0` → `300a`
  en **136 pasos HALTED**; con `1` → once `0x31` en **200 pasos TIMEOUT**. El exit code es **0
  también en TIMEOUT**: el estado hay que leerlo del stderr, no del `$?`.
* Reproduje el claim clásico más fuerte del conjunto: `lt_pass12.mb` (SHA
  `79160ecf…61d2`, 57 511 B) con entrada `01 00 01 01 02 10 00` → stdout `010a` en **81 977
  pasos, HALTED**, coincidiendo con el paso registrado en evidencia ajena.

## El blocker real, medido

No es la VM: es la **capacidad del lenguaje y del codegen disponible**.

| imagen | bytes medidos | capacidad clásica | margen |
|---|---|---|---|
| `mbir_alu_rel.mb` | 57 511 | 59 049 | 1 538 |
| `mbir_cmp_lt.mb` (fuente vivo) | 57 512 | 59 049 | 1 537 |
| `lt_pass12.mb` (artefacto sellado) | 57 511 | 59 049 | 1 538 |

Un **solo kernel** (una comparación, o un ADD/SUB) consume el **97.4 %** de la imagen. La línea
de trabajo `pong1` —`pong1;8,4,4,2,1,-1,0,0,0,0,0;0,0`, 33 caracteres ASCII y 11 campos— no es
expresable con los generadores que existen hoy. Por eso **G2 con `pong1` completo queda
BLOQUEADO**, y el motivo es de codegen/capacidad, no de intérprete ausente.

## Corrección de premisa obligada

El Compose presentaba «7/7 aritmética/control EIR dentro de VM» como si fuera Clásico. Medido en
`raw/11_m0_pipelines.txt`: de los 15 `M0_*/run.json`, **7** dicen `8CC_FAILED_127+GCC_REF` (gcc
nativo, **no** en VM), **7** dicen EIR escrito a mano → HeLL → `.mu` (LMFAO) → **VM Unshackled**, y
**1** (`M0_HELL_VM`) dice Unshackled TARGET_A. Además `M0_HELL_VM/run.json` arranca con **BOM
UTF-8**: la misma clase de defecto que MALDOOM documenta en E7/E8/E9.

## Consecuencia para el plan

La única franja donde hoy existe cálculo dentro de una VM clásica es la de **operandos de un solo
dígito** (tablero 8×4 → valores 0..7). El experimento mínimo que puede desbloquear algo es:
tomar el predicado del rebote vertical (`ny` fuera de rango) como comparación entre operandos de
un dígito, ejecutarlo sobre una imagen MBIR existente, y registrar pasos + SHA. Eso daría, a lo
sumo, *un predicado de tick calculado en VM*. **No** autoriza `ONE_TICK_NO_COLLISION_VM`, ni
`STATEFUL_MIN_PONG_VM`, ni «juego funcionando».
