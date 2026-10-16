# PONG_MIN_SPEC — contrato congelado de MALGAMES/PONG_V0

**Versión del contrato:** `pong1`
**Congelado:** 2026-10-15 (G0) · **Estado:** CONGELADO PARA G1/G2 — cambiar cualquier regla exige subir la versión del contrato y regenerar fixtures; los fixtures congelados no se reescriben en silencio (falsificador 8 del Compose).
**Objetivo:** fijar **qué cuenta como estado, transición, frame y atribución de cómputo**, para que «Malbolge calcula un tick» sea una proposición que puede fallar.

Este documento no afirma nada sobre Malbolge. Define el objeto de prueba.

---

## 1. Estado `S_t`

Campos, en este orden canónico y solo estos:

| Campo | Rango | Notas |
|---|---|---|
| `width` | 2..64 | constante por fixture; viaja en el estado para que el hash sea autocontenido |
| `height` | 2..64 | idem |
| `ball_x` | 0..width-1 | |
| `ball_y` | 0..height-1 | |
| `vel_x` | {-1, +1} | el piloto no admite 0 ni magnitudes >1 |
| `vel_y` | {-1, +1} | idem |
| `paddle_left_y` | 0..height-1 | paleta de **1 celda** (desviación explícita de Pong, no una simplificación oculta) |
| `paddle_right_y` | 0..height-1 | |
| `score_left` | 0..99 | **saturación**, nunca envuelve |
| `score_right` | 0..99 | saturación |
| `tick_index` | 0..2^31-1 | monotónico +1; si excediera el rango el oráculo **falla**, no envuelve |

Cualquier otro dato (semilla, historial, depuración) queda fuera de `pong1`.

## 2. Entrada `I_t`

`left_move`, `right_move` ∈ {-1, 0, +1}. Nada más. La entrada es por tick, no por frame.

## 3. Serialización canónica (bytes, no estructura)

```
estado   := "pong1;" ints "\n"
entrada  := ";" ints "\n"          (solo en la línea de trabajo del oráculo)
ints     := f1 "," f2 "," ... "," f11      (orden de la tabla §1)
```

- Enteros con signo en notación decimal de C: `-1`, `0`, `7`; **sin** ceros a la izquierda, **sin** espacios.
- Separador de línea: **LF (`\n`) únicamente, incluido el último byte**. Sin CRLF, sin BOM. MALDOOM perdió tres rondas de auditoría (E7/E8/E9) por retornos de carro y un BOM en un manifiesto; este contrato lo prohíbe en la raíz.
- El hash se calcula sobre los bytes exactos de la **línea de estado de salida** y sobre los bytes exactos del **frame**; nunca se hashea una estructura intermedia ni se mezcla depuración con los bytes que se hashean.
- Línea de trabajo del oráculo (entrada): `pong1;<11 campos>;<left_move>,<right_move>` → `pong1;<11 campos>` de salida.

## 4. Transición `T(S_t, I_t) → S_{t+1}` — orden total, sin ambigüedad

Los pasos se ejecutan en este orden y solo en este. Un oráculo y un programa Malbolge que difieran en el orden **no son equivalentes**, aunque coincidan en el 90 % de los casos.

1. **tick:** `tick_index' = tick_index + 1`.
2. **paletas antes que la pelota:** `paddle_left_y' = clamp(paddle_left_y + left_move, 0, height-1)`; igual para la derecha con `right_move`.
3. **eje vertical:** `ny = ball_y + vel_y`. Si `ny < 0` o `ny > height-1` → `vel_y' = -vel_y` y `ny = ball_y + vel_y'`. Con `vel_y ∈ {±1}` y `ball_y` en rango, `ny` queda siempre en rango: **no hay segundo rebote vertical en un mismo tick**.
4. **eje horizontal:** `nx = ball_x + vel_x'`.
   - **`nx < 0` (línea de gol izquierda):** si `paddle_left_y' == ny` → golpe de paleta: `vel_x' = +1`, `ball_x' = 0`, sin puntuación. En caso contrario → `score_right' = min(score_right + 1, 99)` y **RESET**: `ball_x' = width/2`, `ball_y' = height/2`, `vel_x' = +1`, `vel_y' = -1` (división entera). Las paletas y el tick no se tocan.
   - **`nx > width-1` (línea de gol derecha):** simétrico — si `paddle_right_y' == ny` → `vel_x' = -1`, `ball_x' = width-1`; si no, `score_left' = min(score_left + 1, 99)` y RESET con `vel_x' = -1`.
   - En otro caso `ball_x' = nx`.
5. Un tick puede contener **rebote vertical y golpe de paleta a la vez**: son independientes por construcción. La prioridad entre ambos está fijada por el orden de §4, no por la casualidad.
6. El resultado de `T` nunca deja el tablero. Un `S_{t+1}` fuera de rango es un fallo del oráculo, no un estado.

`T` es una función **total** sobre estados e entradas válidos; sobre entrada inválida el oráculo sale con código ≠ 0 y un mensaje en stderr, y **no** produce bytes en stdout.

## 5. Render `R(S_{t+1}) → Frame` — separable de `T` por diseño

- Rejilla de `height` filas × `width` columnas, relleno inicial `'.'`.
- Paddles: carácter `'|'` en la columna 0, fila `paddle_left_y'`; columna `width-1`, fila `paddle_right_y'`.
- Pelota: carácter `'o'` en (`ball_x'`, `ball_y'`), **escrita al final**: si pelota y paleta coinciden, la celda muestra `'o'`. Prioridad: puntos → paletas → pelota.
- Bytes del frame: cada fila son `width` caracteres, filas unidas por `\n`, con `\n` final. **El frame no contiene marcadores, ni `tick_index`, ni depuración**: puntuación y tick viven solo en el estado. Así `VM_RENDER` puede afirmarse o negarse sin ambigüedad.

## 6. Unidades y nombres que no se han de confundir

**Un tick actualiza la física; un frame es una representación; un programa Malbolge puede cubrir una unidad o varias.** No son intercambiables y ningún claim mezclará los tres niveles.

Los gates del Compose se nombran así, con alcance explícito:

| Claim | Qué afirma exactamente | Qué **no** afirma |
|---|---|---|
| `ORACLE_ONLY` | `T` y `R` están definidos y son deterministas fuera de la VM | nada sobre Malbolge |
| `ONE_TICK_NO_COLLISION_VM` | la VM calculó `S0→S1` sin eventos de colisión | rebotes, paletas, marcador, frames |
| `STATEFUL_MIN_PONG_VM` | la VM calculó rebote + dos ticks encadenados con estado persistente | Pong completo, interactividad |
| `VM_RENDER_8x4` | la VM calculó los bytes del frame ASCII 8×4 | rendimiento, paletas jugables |
| `FULL_FRAME_VM` / `DELTA_FRAME_VM` | (G5) frame íntegro vs delta calculados por la VM | «jugable» |

## 7. fixtures congelados (conjunto mínimo fijo)

Identificadores, geometría y evento esperado. Los bytes exactos de `S0`, `I0`, `S1` y `Frame1` viven en `tests/fixtures/` y están sellados en `evidence/`; **ningún evento se añade sobre la marcha**.

| id | tablero | evento |
|---|---|---|
| `E1_smoke_8x4` | 8×4 | horizontal sin colisión — el fixture de humo del Compose |
| `E2_vertical_move` | 8×4 | solo cambio de `ball_y` |
| `E3_wall_bounce_v` | 8×4 | `vel_y` invierte en borde superior/inferior |
| `E4_paddle_hit` | 8×4 | `vel_x` invierte por paleta alineada |
| `E5_score_reset` | 8×4 | gol + RESET canónico con saturación |
| `E6_two_ticks_chained` | 8×4 | `T` aplicado dos veces, `tick_index` 0→2 |
| `E7_board_16x8` | 16×8 | fixture ampliado: rebote + paleta + marcador en una secuencia |
| `E8_saturation_99` | 8×4 | `score` en 99 no envuelve |

Los estados `expected_S1` los produce el oráculo en G1 y quedan inmutables; en G2/G3/G4 la salida de la VM se compara **contra estos bytes**, no contra una reimplementación nueva.

## 8. Independencia del oráculo

- El oráculo de referencia está en `oracle/` (C y Python, mismo contrato) y **jamás** participa de la corrida computacional de la VM: genera y verifica expectativas, nada más.
- Ninguna función del oráculo puede ser llamada por el `harness` dentro del proceso que ejecuta la VM. El `harness` solo: carga el programa, fija el presupuesto de pasos/tiempo, pasa bytes por stdin, captura stdout/trace, hashea y compara.
- Falsificador activo registrado: si la traza muestra que C/Python resolvió una coordenada, un rebote o un píxel, el claim pasa a `HOST_COMPUTED` y se retira inmediatamente.

## 9. Rutas de implementación permitidas (no confundirlas)

- `DIRECT_VM` — programa Malbolge que calcula `T`/`R` en una VM clásica real. Claim directo.
- `NESTED_VM` — el juego como bytecode de una segunda VM implementada dentro de Malbolge (p. ej. MEOW). Solo con traza que distinga runner de motor y bootstrap auditado.
- Un éxito en **Unshackled** no demuestra nada en **Clásico**, ni a la inversa: variante y versión van en el manifiesto.

---

## Anexo A — appended 2026-10-15 tras el pre-chequeo de G2 (no reescribe par. 1–9)

Los párrafos 1–9 quedan como se congelaron en G0. Este anexo añade restricciones que la medición
impuso, y se cita junto con ellas.

**A.1 Framing de salida por intérprete.** `Malbolge-Engine/malbolge` añade un `\n` a stdout de
manera incondicional (aunque el programa no emita nada) y `reference_interpreter_classic` no
añade ninguno: el mismo `hello.mal` produce 13 y 12 bytes respectivamente (medido en
`evidence/pong_v0/2026-10-15T195127Z/raw/00_inventory_y_framing.txt`). Por tanto el par. 3 —LF
exclusivo, sin CR, sin BOM, sin depuración mezclada— **no basta**: cualquier artefacto `pong1`
producido por una VM debe registrar en su manifiesto el intérprete exacto y el número de bytes
crudos, y el hash se toma sobre los bytes crudos menos el framing declarado. Prohibido hashear
stdout sin decir qué se recortó.

**A.2 La parada no está en el exit code.** `Malbolge-Engine` devuelve 0 también en TIMEOUT; el
estado real vive en stderr (`steps: N | status: HALTED|TIMEOUT`). La referencia no acepta
`max_steps`, así que un programa que no para gira indefinidamente y hay que envolverla en
`timeout`. Ningún veredicto de `DIRECT_VM` puede apoyarse en `$?`.

**A.3 EOF.** Hay engines que terminan al leer pasado el fin de stdin y otros que ponen `a = 59048`
y continúan. Un programa `pong1` debe consumir **exactamente** los bytes de su línea de trabajo y
nunca depender del EOF. (Divergencia registrada por otros; aquí queda como restricción de diseño,
no como resultado propio.)

**A.4 `NESTED_VM` vía MEOW queda descartada como ruta inmediata.** `meow_vm_malbolge/vm/meow_vm.mal`
(8 220 B, 8 158 bytes NUL) es rechazado por los dos intérpretes clásicos y no tiene evidencia de
ejecución. Seguiría siendo válida una segunda VM dentro de Malbolge escrita desde cero y cargable,
pero hoy no existe.

**A.5 Presupuesto de celdas.** Una imagen MBIR de un solo kernel ocupa 57 511 de 59 049 celdas
(margen 1 538). La línea de trabajo `pong1` son 33 caracteres ASCII con 11 campos. `DIRECT_VM`
sobre `pong1` completo está bloqueado por capacidad/codegen; cualquier intento debe declarar si
reduce **encoding** (operandos de un dígito) o **alcance** (un predicado del tick), y cuál.
