# Limitaciones — MalbolGames / PONG_V0

## De alcance

1. **Nada de esto es Malbolge.** Todo lo demostrado vive en dos oráculos del host. La pregunta
   madre del Compose —*quién calcula el tick*— sigue sin respuesta en la VM.
2. `pong1` congela un tablero pequeño y reglas mínimo-inteligibles. No modela física, colisiones
   entre paletas y bordes, saque con retardo ni marcador visualizado. Un éxito aquí **no** escala
   a Doom: Doom añade fixed-point de 32 bits contra un EIR de 24, WAD, y un framebuffer.
3. El render es separable por decisión, no por necesidad demostrada: puede que un programa
   Malbolge calcule el estado sin poder emitir nunca el frame.

## De las máquinas clásicas (medido, `evidence/pong_v0/2026-10-15T195127Z/raw/`)

4. **Framing distinto por intérprete.** `Malbolge-Engine` añade un newline a stdout (13 bytes);
   `reference_interpreter_classic` emite los 12 exactos. Antes de hashear un frame hay que fijar
   el intérprete y la receta de recorte.
5. **El exit code no señala parada.** `Malbolge-Engine` devuelve **0 también en TIMEOUT**; el
   estado vive en stderr (`steps: N | status: HALTED|TIMEOUT`). La referencia no acepta
   `max_steps`: un programa que no para gira para siempre, hay que envolver en `timeout`.
6. **EOF diverge** entre engines (hallazgo D5 ajeno, no reproducido por mí aquí): la familia
   `vm.c`/Rustbolge termina al leer pasado el fin de stdin; la referencia y `oracle.py` ponen
   `a = 59048` y siguen. Cualquier programa `pong1` que lea de más se comporta de dos maneras
   distintas según el intérprete. **Nunca depender de EOF.**
7. **Capacidad.** 57 511/59 049 celdas por kernel, margen 1 538. No hay un solo programa existente
   que haga dos cosas.
8. **Sin contador de estado ni lectura cruzada de estado en Clásico**, según la evidencia de
   MALDOOM: `CLASSIC_ANCHOR_SMOKE_V1` registra P2/P4/P5 como **negativos** (0 éxitos sobre 2,4 M
   de candidatos) y `STATE_TRANSITIONS/TICK_INC/result.json` dice `found: false`. Un incremento de
   tick en la VM es exactamente lo que se buscó y no se encontró.
9. **`meow_vm_malbolge` no es motor.** Su imagen (`vm/meow_vm.mal`, 8 220 B) contiene 8 158 bytes
   NUL y la rechazan los dos intérpretes. No hay evidencia de que se ejecutara alguna vez.

## De los oráculos

10. Comparten autor: los escribí yo, en dos pasadas, con el mismo papel. Son dos implementaciones
    independientes **de mi lectura del contrato**, no dos lecturas independientes del contrato.
    Un error de interpretación mío aparece en ambos. El acuerdo C↔Python detecta despistes de
    codificación, no de semántica.
11. Los dos oráculos emiten **mensajes de stderr distintos** para la misma línea inválida. El
    contrato solo gobierna (exit ≠ 0, stdout vacío); el stderr no es contractual y no está
    comparado por `compare_oracle.py`.
12. `tests/fixtures/index.tsv` no puede contener su propio hash; queda fuera de su tabla.
13. No hay un tercer motor que valide a los oráculos (property testing, otra implementación, un
    verificador de modelos). La convergencia es a dos vías, no a tres.

## De proceso

14. MALGAMES **no es repositorio git**: la persistencia es filesystem + SHA-256, sin historia
    revisable ni recuperación por commit.
15. `REA` no aporta capacidades de Malbolge despachables en este host (ver
    `docs/PROVENANCE.md`), así que el apoyo que el Compose sugería para la integración no existe
    como superficie ejecutable. El Compose pide además que REA no sea requisito duro: se respeta.

## De la corrida G2 — predicados en VM Clásica (`2026-10-15T203244Z`)

16. Cada predicado solo está demostrado sobre **su dominio finito exacto**: tablero 8×4,
    `by ∈ 0..3`, `vy ∈ {−1,+1}` para `bounce` y `pl, by ∈ 0..3` para `contact`. Nada dice que
    funcione en otro tablero; el generador no fue probado fuera de esos puntos.
17. La **tabla de verdad está horneada en tiempo de codegen** como constante de cada ruta. Lo
    que la VM calcula es qué ruta tomar (incremento/decremento ternario con acarreo y test de
    desbordamiento); la fórmula del predicado no se evalúa en VM. Un claim de «aritmética en
    Malbolge» sería falso con estos artefactos.
18. La **codificación estado→byte la hace el host** antes de escribir stdin. Por tanto la VM no
    ve nunca un estado `pong1`, solo un entero pequeño ya traducido.
19. `bounce` y `contact` son programas **separados que no se encadenan**: la VM no deriva la
    fila post-vertical que consume el segundo, se la damos codificada.
20. Fricción de herramienta, no del motor: la CLI de `MALBOLGE-MB-DATABASE/tools/oracle_classic.py`
    no acepta stdin, hay que importar su `run()`. `run_classic.py` lo hace y lo documenta.
21. El enmarcado de los dos ELF añade **un** `0x0A` al stdout del programa. El recorte es
    explícito (`deframe`) y está medido; si un futuro runner enmarcara distinto, el comparación
    de `run_classic.py` habría que reajustarla.

22. **El ensamblador `LMAO v0.6.0` no es byte-determinista en la cola del `.mb`.** Medido en la
    corrida G2: mismo `.hell` produce prefijos idénticos (34 010/34 105 B y 44 882/45 109 B) y
    colas de 94–227 bytes con contenido variable. La cola es conductualmente inerte (los 4
    binarios dan salidas y pasos idénticos en los 3 intérpretes), pero implica que el `.mb`
    sellado es el artefacto canónico y que **el sha del `.mb` no se re-deriva del `.hell`**. La
    regresión válida es `sha(.hell)` + igualdad de comportamiento.

## De la corrida del encadenado y del techo del kernel (`2026-10-16T003512Z`)

23. **La negativa solo acota el dominio que se probó.** El intento de cadena se declaró sobre la
    franja interior `by ∈ {1,2}` (Anexo A.5: reduce *alcance*, no *encoding*). Los bordes del
    tablero exigen bifurcación condicional y no se ejercitaron: «falla dentro de la franja» no
    implica «falla en todo el dominio», aunque el techo de `CMP_EQ` apunta en esa dirección.
24. **La caracterización de `CMP_EQ` es empírica, no una prueba.** `verdadero ⇔ op1 == 2 ∧
    op2 ∈ {2,3,4}` queda establecida sobre los 25 pares de `0..4 × 0..4` (75 casos sumando `ADD`
    y `SUB`). No se afirma para operandos > 4, ni para streams con más de tres operaciones.
25. **Los intérpretes A y B son el mismo ELF.** `Malbolge-Engine/malbolge` y
    `runners/malbolge-original/malbolge` hashean idéntico (`3257f1ae…`). La corrida son **tres
    ejecuciones sobre dos implementaciones independientes** más el modelo Python; no «tres vías
    reales». La concordancia entre A y B no añade independencia.
26. **12/16 con aciertos por inercia.** Los 12 casos «correctos» de la puerta encadenada son
    aquellos en los que la respuesta es 0 y el kernel imprime `00` para casi cualquier comparación
    que no toque `op1 == 2`. Un acierto de este kernel **no es evidencia de cálculo**: solo el
    patrón de los 4 fallos (los 4 donde debe valer 1) es informativo.
27. **Hubo un arranque de corrida que falló y se conservó.** `evidence/pong_v0/2026-10-16T003152Z/`
    tiene un solo fichero, sin `SHA256SUMS.txt`: construí la ruta del kernel como
    `<ruta_del_script>/<archivo>` en lugar de `<dir_del_script>/<archivo>` y el script abortó antes
    de medir nada. No se borró (la disciplina de evidencia prohíbe reescribir el proceso) y no se
    cuenta como corrida: no hay sellos ni resultados ahí.
28. **«MalbolGames» es la marca visible; `ISyCo Git/MALGAMES` es la ruta canónica.** El README,
    `docs/CLAIMS.md`, `docs/LIMITATIONS.md` y `docs/PROVENANCE.md` usan la marca; los 32 archivos
    de evidencia sellada siguen citando el path viejo, y el Compose ordena una «ruta nueva y
    segregada `MALGAMES/`». Renombrar el directorio sería una operación destructiva sobre la cadena
    de hashes por un cambio de estética, y está descartada a menos que Danny la pida explícitamente
    con la migración de sellos correspondiente.

## Corrección appendida — el punto 14 queda superado (2026-10-16)

29. **Punto 14 superado, no borrado.** El 2026-10-15 MALGAMES **no** era repositorio git y así lo
    dice arriba el punto 14; se deja el texto porque describe el estado bajo el cual se ejecutaron
    las cuatro corridas. Desde el 2026-10-16 el workspace **sí** está versionado y **publicado** en
    `https://github.com/DannyBaanks/MalbolGames` (rama `master`, commit inicial `dec39d9`, 128
    archivos). Lo que **no** cambia: `SHA256SUMS.txt` y los sellos por corrida siguen siendo el
    canon, la verificación sigue siendo `sha256sum -c` (rc=0 en la raíz y en las 4 corridas antes y
    después del push), y el punto 14 sigue siendo la razón por la que la cadena de evidencia **no**
    depende de `git log` para justificarse. La cadena de hashes precede a la historia de git, no al
    revés.
30. **`composes/` no está publicado.** Por decisión de Danny y por el precedente de MALDOOM (602
    archivos versionados, cero del Compose), `composes/COMPOSE_MALGAMES_PONG_V0.md` queda en
    `.gitignore`. Sigue en disco sin tocar y su sha `b1f170b8…` sigue citado arriba; o sea: el repo
    público **no** es autocontenido para auditar el encargo, hay que citar el sha contra el original
    local.

## Límites añadidos por la corrida G3 `2026-10-16T210612Z`

31. **G3 es UNA arista con UN bit en UN disparo.** A emite un byte y HALT. No hay bucle, no hay
    reloj, no hay colas, no hay N nodos, no hay concurrencia medida. Nada de esta corrida autoriza
    a decir «dataflow en Malbolge», «red de workers» ni «físicas simultáneas»; esos claims quedan
    `NOT_DEMONSTRADO` y la pregunta de origen sigue abierta.
32. **`tee` prueba los bytes que salieron de A, no los que B consumió.** Lo que se afirma es que
    el flujo capturado == el stdout crudo de A ejecutado solo == el byte esperado, y que B por
    tubería se comporta **idénticamente en pasos** a B alimentado directo por el host con ese byte
    (C3+C5). La identificación del byte que entra por el stdin de B es una inferencia fuerte sobre
    esa concordancia, no una observación directa: no instrumentamos el syscall de lectura de B.
33. **El modo `eco` no reconoce el símbolo.** No se parchó `MARKERS`, así que el byte cae al
    fallback de eco del generador y B lo reimprime. Sonda C7c: B-ECO con `0x01` emite `'P'`, o sea
    la ruta de despacho existe y no es la que corrió. El modo fuerte es `nota` (B discrimina
    `0x01`/`0x02` por ruta y calcula NOT).
34. **En `eco`, los pasos de B son idénticos en los 8 casos (29 477) porque B no ramifica.** Su
    salida es el byte leído. Por tanto C2 no aporta independencia de ruta en ese modo: la fuerza
    del modo eco está en C3, C5, C6 y la inyectividad sobre `0x30`/`0x31`, no en la discriminación.
35. **La arista no tiene formato de mensaje.** Sin framing de paquete, sin longitud, sin secuencia
    y sin codificación de estado: el enlace entre «el estado `pong1`» y «el byte en el stdin de A»
    lo sigue poniendo el host (hereda el negativo `N3` de G2). `STATEFUL_CROSS_TICK_HANDOFF` — que
    viajen los 11 campos y la segunda VM continúe el tick — sigue sin demostrarse.
36. **El alfabeto `{0x01,0x02}` es un techo de ESTE generador, no una ley de Malbolge.** Sale del
    despacho por valor de `mbir_dispatch_gen.py` y de su margen medido (~26 rutas). Otro codegen
    con otro esquema de dispatch podría tener otro techo; aquí no se probó eso.
37. **E1 y E2 vuelven a ser el mismo ELF** (`3257f1ae98bc…`), igual que en el punto 25. Las cuatro
    parejas {E1,E2}² son tres ejecuciones sobre dos implementaciones, y la única vía independiente
    del binario es el modelo C.
38. **`max_steps = 2 000 000` es un presupuesto, no una medida del coste de encadenar.** Como cada
    programa hace un disparo, no sabemos cuántos pasos costaría una tubería de longitud variable;
    cualquier extrapolación a «k ticks en cadena» está sin medir.
