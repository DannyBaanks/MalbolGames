# Veredicto G1 — oráculo y fixtures de `pong1`

**Run:** `2026-10-15T194755Z` · **Comando de re-verificación:**
`cd evidence/pong_v0/2026-10-15T194755Z && LC_ALL=C.UTF-8 sha256sum -c SHA256SUMS.txt`
(receta por directorio, no desde la raíz: las entradas son relativas al manifiesto — MALDOOM E9, `raw/14`.)

## Qué se demostró

`ORACLE_ONLY = DEMONSTRADO`, con este alcance exacto:

* Dos implementaciones **independendientes** del contrato `pong1` —`oracle/pong_reference.py`
  (Python 3.12) y `oracle/pong_reference.c` (C11 estricto, gcc 13.3, `-Wall -Wextra` sin
  warnings)— producen **bytes idénticos** en los 31 casos comparados.
* 11 transiciones, 2 cadenas (4 y 9 ticks), 3 frames y 15 rechazos.
* Los bytes esperados de `chain_c2` (9 ticks: paleta moviéndose antes que la pelota, clamp,
  rebotes en ambos bordes, gol con reset y marcador 0→1) se derivaron **a mano** del contrato
  de `docs/PONG_MIN_SPEC.md` antes de ejecutar cualquier oráculo, y coinciden byte a byte con
  las dos implementaciones. Eso es un acuerdo a tres vías: lectura del contrato == C == Python.
* Propiedades del contrato verificadas sobre cada oráculo por separado
  (`tests/test_oracle.py`, grupos T1–T6, cero fallos): determinismo en 25 repeticiones, salida
  sin `0x0d` y sin BOM, fallo cerrado (exit ≠ 0 con stdout de cero bytes), composición
  step↔chain, saturación del marcador, clamp de paleta y rechazo de `tick = 2^31−1`.

## Qué NO se demostró

Nada de Malbolge. **Ninguna transición la calculó una VM**: quien computa `S_t → S_{t+1}` en
este run es la CPU del host ejecutando dos oráculos escritos por mí. Los claims
`ONE_TICK_NO_COLLISION_VM`, `STATEFUL_MIN_PONG_VM`, `VM_RENDER_8x4`, `FULL_FRAME_VM` y
cualquier expresión del tipo «juego funcionando» siguen en `NOT_DEMONSTRATED`, y está prohibido
enunciarlos hasta G2.

G2 no se ha intentado en este run. El prerequisite de G2 —identificar una VM clásica ejecutable
y su comando real— sigue abierto y es la única puerta a un `DEMONSTRATED` en Malbolge.

## Defectos encontrados y cómo se trataron

| defecto | tratamiento |
|---|---|
| El harness comparador no pasaba el modo (`step`/`chain`/`render`) al `subprocess`: 16 de 31 casos fallaban con «modo desconocido». | Corregido en `tools/compare_oracle.py`. Los 15 fallos restantes eran reales hasta ese momento y ahora pasan. Queda registrado en `run.json → negative_results`. |
| `tests/fixtures/frames.tsv` se escribió primero con espacios y un salto mal colocado (F3 partido en dos filas). | Descartado y reescrito **antes** de congelar. No hay fixture defectuoso en la evidencia. |
| Los dos oráculos emiten **mensajes de stderr distintos** para la misma línea inválida (`pong1;…;0` con 12 campos: C dice «se esperaban 11 campos», Python «se esperaban 2 movimientos»). | No es una divergencia contractual: el contrato es (exit ≠ 0, stdout vacío) y ambos coinciden. El stderr no es salida contractual. Registrado en `run.json → negative_results` y en `docs/LIMITATIONS.md`. |
| `./build/pong_reference selftest` escribe 12 diagnósticos en stderr (553 B) aunque pasa. | Igual: son sondeos de rechazo del propio selftest. No contamina stdout. |
| `index.tsv` llevaba tamaños en bytes inventados. | Medidos con `stat` y corregidos antes de sellar. `index.tsv` no puede contener su propio hash; por eso no aparece en su tabla ni en `run.json → artifacts`. |

## Estado del pipeline

`G0` contrato congelado + baseline intacto → **cerrado**. `G1` con `ORACLE_ONLY` → **cerrado con
evidencia sellada**. `G2` → **no iniciado**; requiere primero el inventario de VMs y una
verificación en vivo del intérprete que se declare.
