# Procedencia — MalbolGames / PONG_V0

## Nombre: marca visible vs ruta canónica

| capa | valor | por qué |
|---|---|---|
| marca del proyecto | **MalbolGames** | decisión de Danny del 2026-10-15 («Mejor MalbolGames»), aplicada al README y a los títulos de `docs/` |
| workspace en disco | `ISyCo Git/MALGAMES` | lo citan **32 archivos** bajo `evidence/` (recuento con `grep -rl` el 2026-10-16) y lo ordena el Compose: «crear una ruta nueva y segregada `MALGAMES/`», «no renombrar ni mover `MALDOOM` en ningún escenario» (líneas 52–53) |
| alternativa descartada | renombrar el directorio y re-sellar | habría invalidado la cadena de SHA-256 de 4 corridas y convertido 32 citas de ruta en falsedades. Se descartó **antes** de tocar nada, y se consultó con Danny: la opción elegida fue «solo nombre visible», con la justificación textual «nombre histórico, citado por la evidencia sellada; moverlo rompería la cadena de SHA-256» |

Nada de lo demostrado depende del nombre: cada claim cita la ruta **y** el hash del sello.

## Corrección appendida al README (no reescribe la historia)

El README hasta 2026-10-15 describía la corrida `2026-10-15T203244Z` como «G2: 24/24 PASS en VM
Clásico, sellado **(20 entradas)**». Recuento medido el 2026-10-16 sobre el propio fichero:
**`SHA256SUMS.txt` de esa corrida tiene 24 entradas** (y 25 ficheros en disco contando el propio
`SHA256SUMS.txt`). El «20» era un error de transcripción del número de *casos* (24) frente al de
*entradas*; la frase «24/24 PASS» sí era correcta. El README reescrito el 2026-10-16 dice 24.
Se deja constancia aquí porque la disciplina del repo prohíbe corregir un documento sin registrar
la corrección.

## Origen de la línea de trabajo

MALGAMES nace del giro propuesto por Danny el 2026-10-15: seguir preguntando por Doom pero
empezar por una unidad mínima inteligible (Pong) para aislar *quién calcula el tick*. El encargo
ejecutorio es el Compose, y este repo lo guarda verbatim:

| archivo | sha256 | bytes | origen |
|---|---|---|---|
| `composes/COMPOSE_MALGAMES_PONG_V0.md` | `b1f170b8e8e53617bfb5b4f730827a4731581bb10a3f240826cd8d46ed3f430a` | 22 426 | copia íntegra de `~/Descargas/COMPOSE_MALGAMES_PONG_V0.md`, que a su vez es la unidad 01 del Encargo MalDoom |
| `docs/PONG_MIN_SPEC.md` | G0: `045ba24a796ca30dbbd1554a3733cbf23b787a6823373e67b45e901f9f5bc496` · tras el Anexo A appended: `a927f2786db31234c471d74a6d34d3efeb3a8633ecc4a0c092b86d0ffb3e7889` (10 359 B) | — | escrito en G0; contrato `pong1` congelado. Los par. 1–9 **no se reescribieron**: el pre-chequeo de G2 añadió un anexo al final, como manda la disciplina de evidencia (append, no rewrite) |

## Baseline MALDOOM: intacto

* `MALDOOM` en HEAD corto **`32a7392`**, `git status --short` vacío al medir (2026-10-15).
* Cadena de sellos al medir: **53 manifiestos / 445 entradas / 436 alineadas a tres vías /
  9 irreversibles / 0 ausentes**.
* **MALGAMES no escribió nunca dentro de MALDOOM.** Todas las lecturas fueron de sólo lectura.
* Los archivos canónicos de MALDOOM —`vendor/`, `SHA256SUMS.txt`, `evidence/E1..E9`— no se
  renombraron, ni se movieron, ni se reescribieron. El pipeline de sellos no se tocó.
* El monorepo `ISyCo` no tiene remote y no se empujó nada. MALGAMES tampoco es repositorio git.
  *(Fue cierto al medir, 2026-10-15; superado el 2026-10-16 — ver «Publicación del workspace» abajo.)*

## Premisas del Compose corregidas contra los archivos

| premisa del Compose | estado | evidencia |
|---|---|---|
| «REA ya tiene una integración de Malbolge» | **VERIFIED_ABSENT** en la superficie ejecutable | `rea_discover("malbolge")` → `count 0` de `catalog_count 210`, medido de nuevo hoy; `rea_describe("trace_malbolge")` → *Unknown capability*; CLI `rea@6.5.0` → `COMMAND_NOT_FOUND`. El código de la familia `malbolge-provider` **existe en el árbol** (`~/Development/rea/src/{domain,contracts}/malbolge/*`) y `dist/cliCommandNames.js` lista `inspect/trace/decompile_malbolge` solo para el adaptador MCP. Nada despachable hoy. |
| «7/7 de aritmética/control EIR dentro de VM» como Clásico | **FALSA tal como se enuncia** | 15 `MALDOOM/evidence/M0_*/run.json`: **7** `8CC_FAILED_127+GCC_REF` (gcc nativo, **no** en VM), **7** `EIR(escrito a mano)->HeLL->mu(LMFAO)->VM` en **Unshackled**, **1** Unshackled TARGET_A. Medido en `evidence/pong_v0/2026-10-15T195127Z/raw/11_m0_pipelines.txt`. |
| `meow_vm_malbolge` como apoyo posible | **CERRADO: no es motor** | `vm/meow_vm.mal` (8 220 B) con 8 158 bytes NUL, rechazado por los dos intérpretes clásicos; sin `run.json`, sin SHA, sin log de ejecución |
| «Doom en Malbolge» como objetivo alcanzable con más esfuerzo | **Reencuadrado** | El muro medido sigue siendo presupuesto (pasos/tick, getc por byte, EIR de 24 bits contra fixed-point de 32, 59 049 celdas). Pong mínimo es superior científicamente porque hace falsables M4/M5/M6. |

## Hechos de máquina verificados **por mí en vivo**, sin intermediarios

Todos en `evidence/pong_v0/2026-10-15T195127Z/raw/`. Ninguno se tomó de informe ajeno:

1. `Malbolge-Engine/malbolge` (ELF, 17 336 B) y `workspace/assembly/malbolge/reference_interpreter_classic`
   (ELF, 16 536 B) ejecutan `MALDOOM/vendor/classic/hello.mal` (64 B). stdout **13** vs **12** bytes.
2. `truth_machine.mal` (255 B) ramifica sobre stdin dentro de la VM: `0` → `300a` @136 HALTED;
   `1` → 11×`0x31` @200 TIMEOUT. Exit code 0 en ambos.
3. `lt_pass12.mb` reproducido: SHA `79160ecf906ce3a44a90aed9320954890e04b9444a3da30ad9c88e7cbecb61d2`,
   57 511 B, entrada `01 00 01 01 02 10 00` → stdout `010a` @**81 977** pasos, HALTED.
4. Longitudes de imagen: `mbir_alu_rel.mb` 57 511 B, `mbir_cmp_lt.mb` 57 512 B (fuente vivo),
   `lt_pass12.mb` 57 511 B (sellado). **El fuente vivo ya no hashea como el artefacto sellado**
   (no comparé los bytes, solo las longitudes).

## Procedencia del código de los oráculos

`oracle/pong_reference.py` y `oracle/pong_reference.c` los escribí yo en este encargo, sin copiar
de ningún repositorio, a partir de `docs/PONG_MIN_SPEC.md`. Los esperados de los fixtures se
derivaron **a mano del contrato antes de ejecutar** cualquier oráculo. No comparten una sola línea
de código ni dependen el uno del otro en tiempo de ejecución.

## Autoría de terceros citada (no verificada por mí en este run)

`LMAO v0.6.0` (Matthias Lutter) — verificado solo `--help`. Los números 25/25, 12/12 de los
kernels MBIR, y la taxonomía de divergencias D1–D5 de `malbolge-differential` proceden de archivos
ajenos y se citan como registro ajeno, no como resultado propio.

## Procedencia del código de la corrida G2 (`2026-10-15T203244Z`)

`vm/classic/pong_codegen.py` y `vm/classic/run_classic.py` los escribí yo en este encargo. No
copian una línea del generador upstream: lo **importan** en memoria, sustituyen el dict `MARKERS`
y llaman a su `generate()`. Todo el HeLL emitido sigue siendo el de `mbir_dispatch_gen.py`, sin
editar. Pruebas registradas en la propia corrida: diff estructural de 16 líneas = 8 constantes
(`raw/07`), `MALBOLGE-MB-DATABASE` en HEAD `d479473` con `git status --porcelain` vacío y sha del
generador `c756fac6…`, y re-hash del upstream dentro del codegen que aborta si cambia.

## Premisa del pre-chequeo que esta corrida refine

El pre-chequeo (`2026-10-15T195127Z`) dejó escrito que G2 estaba bloqueado por
**capacidad/codegen, no por falta de VM**. Sigue siendo cierto, pero la parte de *codegen* estaba
subestimada: el bloqueo no era la ausencia de un generador sino **una tabla de marcadores fijada
en el módulo y no expuesta por CLI**. Con esa tabla parametrizable, el despacho ya funcionando
emite predicados en Clásico sin tocar ninguna otra pieza (`raw/10` registra la línea base intacta:
mismas 8 rutas, marcas `P,R,U,L,S,A,B,M`, 38 450–42 904 pasos).

También se midió el techo real del despacho: 24 rutas ensamblan (56 361 celdas, margen 2 688) y
32 rutas **no** ensamblan — `lmao` sale con `rc=1` y `Free space exceeded (Add Malbolge command)`,
sin emitir `.mb`. Por tanto «no cabe» deja de ser una afirmación genérica y pasa a ser una cota
con número y error exacto.

## Procedencia del código de la corrida del encadenado (`2026-10-16T003512Z`)

Los cinco scripts de `vm/nested/` los escribí yo en este encargo, ninguno copia una línea de
código ajeno:

| archivo | qué hace | de dónde sale lo que ejecuta |
|---|---|---|
| `replay_alu_rel.py` | control de legitimidad: 25 vectores con doble verificación (hex esperado **y** pasos documentados) | los 25 vectores están **transcritos tal cual** de `ALU_REL_STATUS.md` (registro ajeno); la lista `VECTORES` es literal, no generada |
| `audit_alu_rel_isa.py` | rejilla de operadores sobre la ISA del kernel (`stream(op,a,b) = PUSH a PUSH b OP OUT HALT`) | escritura propia; los opcodes (`HALT 0x00`, `PUSH_CONST 0x01`, `ADD 0x02`, `SUB 0x03`, `CMP_EQ 0x04`, `OUT_BYTE 0x10`) se leen del docs upstream |
| `matriz_operadores.py` | análisis **offline** de un informe de auditoría: matrices por op, vocabulario imprimible, diagonal de `CMP_EQ`, intersección con `0..3` | no toca la VM; entra por stdin/argumento el JSON ya sellado |
| `extracta_estructura_kernel.py` | extrae etiquetas de resultado y constantes ROT del HeLL del kernel | **importa en memoria** `MALBOLGE-MB-DATABASE/tools/mbir_alu_rel_gen.py` (sólo lectura) y llama a su `generate()`; el fuente vivo no se edita ni se re-hashea como artefacto |
| `pong_nested.py` | la cadena `bounce → contact` por dataflow, con la puerta encadenada | streams propios sobre el kernel sellado |
| `mbir_alu_rel_pass25.mb` | copia local del kernel reutilizado | copia byte-idéntica del artefacto sellado upstream, sha `3b6c011bf3f8f1c7bb610b99812956d7268719557b81ec7e85d481edf240f977`; los scripts **abortan** si el sha no coincide |

`vm/classic/trit_mask_probe.py` y `vm/classic/probe_sizes/*.mb` son de la misma ventana de trabajo:
el probe pregunta si una **máscara de trits** es expresable con `crazy`+`rot` (respuesta: más débil
de lo que la idea necesita), y `probe_sizes/` contiene cinco `.mb` de ejemplo upstream
(`example_adder.mb` 55 725 B, `example_digital_root.mb` 31 755 B, `example_cat_halt_on_eof.mb`
20 776 B, `example_hello_world.mb` 14 796 B, `example_simple_cat.mb` 2 051 B) copiados **solo como
medida de tamaño** de autoría HeLL directa. No son artefactos de este repo ni Claim alguno descansa
en ellos; se conservan porque el «Punto de continuación» 2 del README usa esa medida.

## Advertencia de independencia (medida, no supuesta)

`Malbolge-Engine/malbolge` y `MALBOLGE-MB-DATABASE/runners/malbolge-original/malbolge` **son el
mismo ELF**: sha `3257f1ae98bcd3e86a1b93d1b53a4b3d3512d8265cb7052f2bcb56b1e95ea231` en ambos,
verificado de nuevo el 2026-10-16. Por tanto «A == B == C» en las corridas significa **tres
ejecuciones sobre dos implementaciones independientes** (los dos ELF, que comparten origen) más el
modelo Python de upstream. Los pasos idénticos entre A y B no son evidencia de convergencia.

## Baseline de la corrida del encadenado

Medido antes de escribir nada: `MALBOLGE-MB-DATABASE` en HEAD `d479473` con
`git status --porcelain` vacío (0 líneas modificadas) y sin ningún push. `MALDOOM` intacto. El
monorepo `ISyCo` no tiene remote y no se empujó nada. Ningún fixture de `tests/fixtures/`, ningún
oráculo y ningún documento upstream se modificaron durante la corrida.

## Publicación del workspace (`2026-10-16`, a pedido expreso de Danny)

| dato | valor |
|---|---|
| remoto | `https://github.com/DannyBaanks/MalbolGames` — **PUBLIC**, rama `master` |
| commit inicial | `dec39d91dcd60dfc63e938f3b4c91aeae0837e34` (128 archivos versionados) |
| excluido por `.gitignore` | `composes/` (el encargo verbatim), `build/`, `__pycache__/`, `*.pyc`, `.DS_Store` |
| por qué se excluye `composes/` | precedente medido: MALDOOM publica 602 archivos y **cero** del Compose. El brief es el encargo, no la evidencia; su sha `b1f170b8…` sigue citado arriba y el fichero sigue en disco sin tocar |
| dianas de esa exclusión | **8** archivos versionados citan `COMPOSE_MALGAMES_PONG_V0.md` o su sha: `README.md`, `docs/LIMITATIONS.md`, `docs/PROVENANCE.md` y **5 ficheros de evidencia sellada** (`…T194755Z/run.json`, `…T203244Z/run.json` y `verdict.md`, `…T003512Z/run.json` y `verdict.md`). En el repo público esas citas apuntan a una ruta que no existe: quedan como referencia al artefacto local, auditable por su sha. No se tocó ningún sellado para «resolverlo», porque reescribir evidencia está prohibido y rompería su hash |
| verificación post-push | `sha256sum -c` rc=**0** en la raíz y en las 4 corridas selladas; `HEAD` local == `refs/heads/master` remoto; 4 ficheros muestreados (`README.md`, `SHA256SUMS.txt`, `vm/nested/mbir_alu_rel_pass25.mb`, `docs/PROVENANCE.md`) tienen el mismo sha256 leídos por la API de GitHub que en disco; `core.autocrlf=false`, así que git no normalizó ninguna línea |
| orden de autoridad | el sello hasheado **precede** al commit: las cuatro corridas se cerraron siendo el workspace no-git. El repo es una capa de historia, no de validación |

Lo que **no** cambió con la publicación: ningún claim de `docs/CLAIMS.md` subió de estado, ningún
fixture se retocó, y MALDOOM / `MALBOLGE-MB-DATABASE` / el monorepo ISyCo siguen sin empujar
(`ISyCo` no tiene remote). El punto 14 de `docs/LIMITATIONS.md` queda superado por el punto 29 del
mismo fichero, que registra la corrección sin borrar el texto original.

## Procedencia del código de la corrida G3 (`2026-10-16T210612Z`)

Los tres scripts nuevos de `vm/classic/` los escribí yo en este encargo; ninguno copia código ajeno:

| archivo | qué hace | de dónde sale lo que ejecuta |
|---|---|---|
| `handoff_codegen.py` | codegen de la arista: A emite `0x01`/`0x02` crudos, B calcula NOT / swap / eco, y `expect` deriva la composición del oráculo | **importa en memoria** `MALBOLGE-MB-DATABASE/vm_malbolge/tools/mbir_dispatch_gen.py` (solo lectura) y llama a su `generate()`; re-verifica su sha `c756fac6…` en cada emisión y **aborta** si cambió. La sustitución de `MARKERS` ocurre en memoria; con `--variant eco` **no** se sustituye nada, se usa el generador intacto |
| `run_handoff.py` | levanta la **tubería real** `E1 A.mb < in \| tee Aout \| E2 B.mb` y evalúa C1..C7 | ejecuta los dos ELF Clásicos y consulta el modelo C **solo** para la expectativa; el oráculo nunca está en la tubería |
| `probe_hell_bytes.py` | sondas `markers` / `receivers` / `ascii`: qué forma de constante HeLL imprime un byte crudo | usa la CLI upstream para generar un despacho de 3 rutas y sustituye únicamente la línea `ROT` de `dispatch_01`; `ascii` delega en `run_classic.py` para no duplicar el protocolo de salida |

Los cuatro pares `.hell`/`.mb` (`pong_bounce_raw_v0`, `pong_not_v0`, `pong_not_v0_MUTANT_swap`,
`pong_echo_v0`) son salida ensamblada por LMAO de esos `.hell`; ninguno reemplaza a un artefacto
sellado. `pong_bounce_v0.mb` se usó como productor del modo `eco` **sin modificarlo**: sha
`177e7fce…` idéntico antes y después, y `sha256sum -c SHA256SUMS.txt` rc=0 en la raíz (24 entradas
entonces) como control previo y posterior.

Baseline de esta corrida: `MALBOLGE-MB-DATABASE` en HEAD `d479473` con `git status --porcelain` =
0 líneas; `mbir_dispatch_gen.py` `c756fac6…`, `oracle_classic.py` `5dae8f31…`, `lmao` `5a6039ef…`
(idénticos a los registrados en G2). Los ELF Clásicos comparten sha `3257f1ae98bc…`, así que las
cuatro parejas {E1,E2}² son **tres ejecuciones sobre dos implementaciones**, no cuatro vías.

## Enmienda fechada al punto «dianas de esa exclusión» (2026-10-16, tras G3)

El recuento de **8** archivos versionados que citan el Compose se midió en el commit inicial
`dec39d9`. Tras sellar G3 son **9**: se suma
`evidence/pong_v0/2026-10-16T210612Z/run.json`. No se reescribió la fila de arriba porque describe
el estado bajo el que se publicó; se deja y se añade esta enmienda. Consecuencia práctica sin
cambio: en el repo público esas citas apuntan a `composes/…`, ruta excluida por `.gitignore`, y el
encargo se audita contra su sha `b1f170b8e8e53617bfb5b4f730827a4731581bb10a3f240826cd8d46ed3f430a`.
