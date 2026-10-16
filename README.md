# MalbolGames — cómo representa Malbolge un videojuego

Pregunta de investigación: **¿quién calcula `S_t → S_{t+1}` en un videojuego escrito en Malbolge?**
No es un port de Doom. Es la unidad mínima inteligible (Pong) que hace falsables los escalones M4,
M5 y M6 de la escalera MalDoom.

**Nombre.** El proyecto se llama **MalbolGames**. El workspace en disco sigue siendo
`ISyCo Git/MALGAMES`, y no es timidez: ese nombre lo citan **32 archivos de evidencia sellada** y
lo ordena el propio Compose (`composes/COMPOSE_MALGAMES_PONG_V0.md`, líneas 52–53: crear «una ruta
nueva y segregada `MALGAMES/`», «no reescribir `MALDOOM/`», «no renombrar ni mover MALDOOM en
ningún escenario»). Mover el directorio invalidaría la cadena de SHA-256. Cambiar solo la marca
visible deja **cero hashes rotos**.

**Estado a 2026-10-16:** `G0` contrato congelado ✅ · `G1` oráculo doble y fixtures sellados ✅ ·
`G2` **dos predicados de la transición calculados dentro de la VM Clásica** ✅ · el intento de
encadenarlos en un solo programa es una **NEGATIVA MEDIDA** ❌ (causa: capacidad del kernel MBIR,
no el tamaño). Ningún juego corre. Ningún frame lo calcula Malbolge. Ver `docs/CLAIMS.md`.

## Qué SÍ tenemos — tabla DEMOSTRADO / NEGATIVA / NOT_DEMONSTRADO

Cada línea dice VM, cálculo y prueba, porque sin esas tres cosas el enunciado no es usable.

| escalón | claim | estado | qué afirma exactamente | sello |
|---|---|---|---|---|
| G0 | `CONTRATO_PONG1_CONGELADO` | **DEMOSTRADO** (definición, no ejecución) | `pong1` es un contrato cerrado: orden total, serialización canónica, saturación sin envoltura, render separable, fallo cerrado | `docs/PONG_MIN_SPEC.md` sha `a927f278…` |
| — | `MAQUINA_CLASICA_DISPONIBLE` | **DEMOSTRADO** | dos ELF Linux ejecutan la referencia Clásica; `truth_machine.mal` **ramifica sobre stdin dentro de la VM** (136 pasos HALTED); `lt_pass12.mb` reproducido a 81 977 pasos con SHA exacta | `evidence/pong_v0/2026-10-15T195127Z/` (15 entradas) · `SHA256SUMS.txt` `e214ba1a…` |
| G1 | `ORACLE_ONLY` | **DEMOSTRADO** | **la CPU del host** calcula el tick: 31/31 verificaciones byte-idénticas entre Python 3.12 y C11/gcc 13.3, sobre fixtures derivados a mano del contrato **antes** de ejecutar | `evidence/pong_v0/2026-10-15T194755Z/` (26 entradas) · `SHA256SUMS.txt` `c6b8dc6a…` |
| G2 | `ONE_PREDICATE_FINITE_DOMAIN_CLASSIC_VM` | **DEMOSTRADO** | **la VM Malbolge Clásica** calcula dos predicados del tick sobre dominio finito: `bounce_vertical` 8/8 y `contact_gate` 16/16, con salida **y pasos** idénticos en tres intérpretes; control de selectividad con mutante | `evidence/pong_v0/2026-10-15T203244Z/` (24 entradas) · `SHA256SUMS.txt` `c16190d9…` |
| — | `HARNESS_FIEL_A_CORPUS_UPSTREAM` | **DEMOSTRADO** | el harness de MalbolGames reproduce los 25 vectores sellados de `ALU_REL` en **salida y en pasos** (58 689–83 478), 0 desacuerdos. Sin este control, el negativo de abajo no valdría nada | `…/2026-10-16T003512Z/raw/replay_alu_rel.json` |
| — | `MBIR_ALU_REL_IS_A_CLASSIFIER` | **DEMOSTRADO** (techo medido) | el kernel «Relational ALU» es un **clasificador acotado de operandos**, no una ALU (detalles abajo) | `evidence/pong_v0/2026-10-16T003512Z/` (19 entradas) · `SHA256SUMS.txt` `444f3ef4…` |
| G2+ | `TICK_CHAIN_SINGLE_PROGRAM_VM` | **NEGATIVA MEDIDA** | encadenar `bounce → contact` en un solo programa por *dataflow* sobre el kernel sellado **falla**: condición (a) FALSA (0/4 en la derivación, 12/16 en la puerta) | mismo sello, `run.json.condiciones_falsables_pactadas` |

## Qué NO tenemos

- **El tick completo dentro de la VM.** `ONE_TICK_NO_COLLISION_VM` → `NOT_DEMONSTRADO`. Lo que
  corre en Clásico son **predicados sueltos**, cada uno en su propio programa, sobre enteros ya
  traducidos por el host antes de escribir stdin.
- **Estado.** `STATEFUL_MIN_PONG_VM` → `NOT_DEMONSTRADO`. No hay contador de estado ni lectura
  cruzada de estado en Clásico: MALDOOM registra P2/P4/P5 como negativos (0 éxitos sobre 2,4 M de
  candidatos) y `STATE_TRANSITIONS/TICK_INC` dice `found: false`.
- **Render ni frame.** `VM_RENDER_8x4` y `FULL_FRAME_VM` → `NOT_DEMONSTRADO`.
- **Framing.** La VM no sabe leer la línea `pong1;…` carácter a carácter. Sin esto **ningún**
  resultado futuro puede llamarse `DIRECT_VM`, y ninguno de los predicados sellados lo es: la
  codificación estado→byte la hizo el host antes de escribir stdin.
- **MALPONG.** No existe. `JUEGO_FUNCIONANDO` está **prohibido** por el Compose hasta que la
  transición se calcule dentro de la VM.
- **Aritmética de dominio variable.** Ni suma general, ni clamp, ni envoltura del marcador
  (ver el techo abajo).

## El techo medido del kernel (esto es lo que bloquea el siguiente escalón)

El kernel MBIR reutilizado es `alu_rel_pass25.mb` (57 511 B de 59 049 celdas clásicas, margen
1 538; sha `3b6c011b…`). Su corpus 25/25 es **real y fiel** — los reprodujimos enteros — pero su
alcance no es el que sugiere el número:

- **`CMP_EQ` no es la igualdad.** Sobre la rejilla 5×5 (0..4 × 0..4) es verdadero exactamente en
  `{(2,2),(2,3),(2,4)}` ⇔ `op1 == 2 ∧ op2 ∈ {2,3,4}`. Falla `0==0`, `1==1`, `3==3`, `4==4` y da
  falso positivo en `2==3` y `2==4`.
- **Vocabulario imprimible acotado a 5 valores:** `{0x00, 0x01, 0x02, 0x05, 0x07}`. El valor **3**
  del tablero 8×4 **no es imprimible** por este kernel, con independencia del stream.
- **`ADD` 5/25 y `SUB` 4/25** de aciertos sobre la rejilla: solo funcionan en la franja que los
  vectores sellados ya ejercitan.
- **Tres operaciones encadenadas pierden el valor:** el stream que derivaba la fila post-vertical
  imprime `0xc6` en los cuatro puntos interiores.
- **Mecanismo, leído del HeLL sellado:** 6 etiquetas de resultado (`sum_is_2/5/7`,
  `diff_is_0/1/2_from_phase2`) materializadas cada una por **una constante ROT** de
  `{0, 3, 6, 15, 21}`. El «resultado» es clasificación, no aritmética. Upstream ya lo dice en
  `M2_ALU_STATUS.md` («Small-operand lookup … the result byte is ROT 0, 3, 6, 15, or 21») y lista
  *Arbitrary Signed* como no demostrado: esta corrida **afina** su documentación, no la contradice.

Y el dato complementario, del escalón anterior: el **despacho** por enumeración sí cabe — 8 rutas
→ 35 515 B, 16 → 45 949 B, 20 → 51 683 B, **24 → 56 361 B (margen 2 688) ensambla**; **32 rutas NO**
(`lmao` rc=1, `Free space exceeded (Add Malbolge command)`, sin emitir `.mb`). Crecimiento
≈ 1 180 celdas por ruta. O sea: el muro no es el despacho, es el kernel.

## Layout

```
composes/   COMPOSE_MALGAMES_PONG_V0.md        el encargo, verbatim (sha b1f170b8…)
docs/       PONG_MIN_SPEC.md                   contrato pong1 (par. 1-9 + Anexo A appended)
            CLAIMS.md LIMITATIONS.md PROVENANCE.md
oracle/     pong_reference.py  pong_reference.c  dos implementaciones independientes
harness/    compare_oracle.py                  igualdad byte a byte C <-> Python (JSON puro)
tests/      test_oracle.py                     contrato T1-T6 sobre cada oraculo
            fixtures/                          8 fixtures congelados + index.tsv + SHA256SUMS.txt
vm/classic/ pong_codegen.py                     extension del codegen upstream (tabla opcode->'0'/'1')
            run_classic.py                     ejecuta el .mb en 3 interpretes Clasicos y compara
            pong_bounce_v0.{hell,mb}           predicado bounce_vertical, 8 rutas, 34105 B
            pong_contact_v0.{hell,mb}          predicado contact_gate, 16 rutas, 45109 B
            trit_mask_probe.py                 probe: ¿es expresable una mascara de trits en Clasico?
            probe_sizes/                       .mb de ejemplo upstream, usados solo como medida
vm/nested/  pong_nested.py                      intento de cadena bounce->contact por dataflow
            replay_alu_rel.py                  control: 25 vectores sellados, salida Y pasos
            audit_alu_rel_isa.py               rejilla de operadores 75 casos
            matriz_operadores.py               analisis offline del informe de auditoria
            extracta_estructura_kernel.py      etiquetas y constantes ROT del HeLL sellado
            mbir_alu_rel_pass25.mb             copia del kernel (sha 3b6c011b…)
evidence/   pong_v0/2026-10-15T194755Z/        G1: 31/31 PASS, sellado (26 entradas)
            pong_v0/2026-10-15T195127Z/        G2 pre-chequeo: maquinas verificadas en vivo (15)
            pong_v0/2026-10-15T203244Z/        G2: 24/24 PASS en VM Clasico, sellado (24 entradas)
            pong_v0/2026-10-16T003152Z/        arranque fallido (error de ruta), 1 fichero, sin sello
            pong_v0/2026-10-16T003512Z/        cadena: NEGATIVA MEDIDA + techo del kernel (19)
```

## Reproducir G1

```bash
cd "/home/danny/Development/ISyCo Git/MALGAMES"
gcc -O2 -std=c11 -Wall -Wextra -o build/pong_reference oracle/pong_reference.c
python3 oracle/pong_reference.py selftest && ./build/pong_reference selftest
python3 harness/compare_oracle.py --root .      # -> 31 checks, byte_equal_cross_oracle true
python3 tests/test_oracle.py --root .           # -> T1-T6, 0 fallos
cd evidence/pong_v0/2026-10-15T194755Z && LC_ALL=C.UTF-8 sha256sum -c SHA256SUMS.txt
```

## Reproducir el pre-chequeo de G2 (todo de sólo lectura)

```bash
E="/home/danny/Development/ISyCo Git/Malbolge-Engine/malbolge"
"$E" "/home/danny/Development/ISyCo Git/MALDOOM/vendor/classic/hello.mal" 100000 </dev/null
printf 0 | "$E" "/home/danny/Development/ISyCo Git/MALDOOM/vendor/classic_synthesis/malpad/truth_machine.mal" 200
cd "/home/danny/Development/ISyCo Git/MALBOLGE-MB-DATABASE"
printf '\x01\x00\x01\x01\x02\x10\x00' | ./runners/malbolge-original/malbolge \
    vm_malbolge/evidence/artifacts/lt_pass12.mb 600000     # -> 010a @ 81977 pasos
```

## Reproducir G2 — predicados en VM Clásica (solo lectura fuera de MalbolGames)

```bash
cd "/home/danny/Development/ISyCo Git/MALGAMES/vm/classic"
python3 pong_codegen.py check --kind bounce            # 8/8 vs oraculo
python3 pong_codegen.py check --kind contact           # 16/16 vs oraculo
python3 pong_codegen.py emit  --kind bounce  -o pong_bounce_v0.hell
python3 pong_codegen.py emit  --kind contact -o pong_contact_v0.hell
LMAO="../../MALBOLGE-MB-DATABASE/third_party/lmao/bin/lmao"
"$LMAO" -o pong_bounce_v0.mb  pong_bounce_v0.hell      # 34105 B
"$LMAO" -o pong_contact_v0.mb pong_contact_v0.hell     # 45109 B
python3 run_classic.py --kind bounce                   # 8/8 PASS, A==B==C, exit 0
python3 run_classic.py --kind contact                  # 16/16 PASS, exit 0

# OJO: reensamblar NO reproduce el sha del .mb. LMAO v0.6.0 deja una cola de 94-227 bytes
# con contenido variable (prefijo y comportamiento identicos). El .mb sellado es el canon;
# la regresion valida es sha(.hell) + igualdad de comportamiento. Ver LIMITATIONS par. 22.
cd ../../evidence/pong_v0/2026-10-15T203244Z && LC_ALL=C.UTF-8 sha256sum -c SHA256SUMS.txt
```

## Reproducir la corrida del negativo (2026-10-16)

```bash
cd "/home/danny/Development/ISyCo Git/MALGAMES/vm/nested"
python3 replay_alu_rel.py run          # ~4 min   -> 25/25 FIEL_A_EVIDENCIA_SELLADA, rc 0
python3 audit_alu_rel_isa.py run       # ~6 min   -> rejilla de 75 casos, desacuerdos 0
python3 pong_nested.py run             # ~2.5 min -> rc 1 (12/16): el NEGATIVO es el resultado
python3 matriz_operadores.py <informe.json>
python3 extracta_estructura_kernel.py
cd ../../evidence/pong_v0/2026-10-16T003512Z && LC_ALL=C.UTF-8 sha256sum -c SHA256SUMS.txt
```

Los tres primeros abortan si el sha del kernel no es `3b6c011b…`. Todo es de sólo lectura fuera de
este workspace; `MALBOLGE-MB-DATABASE` queda en HEAD `d479473` con 0 archivos modificados.

## Reglas de este repo

1. Prohibido decir «juego funcionando», «frame de Malbolge», «100 %» o «demostrado» sin nombrar
   la VM, el cálculo y la prueba independiente. Eso es `HOST_COMPUTED` y retira el claim.
2. Ninguna evidencia se reescribe: se añaden anexos. Los hashes viejos se citan junto con los nuevos.
3. Sin CR y sin BOM en cualquier artefacto contractual; el stderr no es salida contractual.
4. MALDOOM, su pipeline de sellos y el monorepo ISyCo no se tocan ni se empujan.
5. Un resultado en Unshackled no afirma nada en Clásico, ni al revés.
6. Un negativo medido se sella igual que un positivo: con entorno, comando, salida cruda y hash.

## Honestidad que hay que arrastrar

- Los intérpretes A y B (`Malbolge-Engine/malbolge` y `runners/malbolge-original/malbolge`) son
  **el mismo ELF** (sha `3257f1ae…` idéntico). Son tres ejecuciones sobre dos implementaciones
  independientes más el modelo Python. No se infla a «tres vías reales».
- El enmarcado difiere por intérprete: los dos ELF añaden **un** `0x0A`; el oráculo Python no. El
  recorte es explícito (`deframe`) y está medido.
- `Malbolge-Engine` devuelve **exit 0 también en TIMEOUT**: el estado vive en stderr.
- Los dos oráculos comparten autor (los escribí yo): el acuerdo C↔Python detecta despistes de
  codificación, no de semántica.
- MalbolGames **no es repositorio git**: la persistencia es filesystem + SHA-256, sin historia
  revisable ni recuperación por commit.
- La caracterización `CMP_EQ ⇔ op1 == 2 ∧ op2 ∈ {2,3,4}` es **empírica en 0..4 × 0..4**; no se
  afirma para operandos mayores.

## Punto de continuación

El escalón que estaba abierto —encadenar `bounce → contact` dentro de un mismo programa para que
la VM derive la fila post-vertical en lugar de recibirla codificada— **se intentó y quedó cerrado
como negativa medida** en `evidence/pong_v0/2026-10-16T003512Z/`. La causa está localizada con
precisión, así que el siguiente paso tiene dos rutas disjuntas y ambas declarables:

1. **Kernel con igualdad real** — `CMP_EQ` reflexivo sobre 0..3, o `CMP_LT`/`CMP_GT` multiplexados.
   Es trabajo de `MALBOLGE-MB-DATABASE`, y el margen es de **1 538 celdas**: no es gratis ni
   evidente. Coste: desconocido; es la única vía que levanta el techo medido en vez de esquivarlo.
2. **Autoría HeLL directa** — estilo `example_adder.hell` (bucles por estado de ciclo xlat2,
   55 725 B funcionando), la vía con la que se demostró `CMP_LT` fuera del generador. Permite un
   programa que **lea** la codificación y calcule, en vez de despachar por tabla. Coste: autoría a
   mano + ensamblado; no requiere tocar upstream.

Detalle en `evidence/pong_v0/2026-10-16T003512Z/verdict.md`, `docs/CLAIMS.md` (anexo) y
`docs/LIMITATIONS.md` §16–27.
