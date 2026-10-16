/* MALGAMES/PONG_V0 — oraculo de referencia en C, contrato `pong1`.
 *
 * Espejo exacto de oracle/pong_reference.py: misma serializacion, mismo orden de transicion
 * (docs/PONG_MIN_SPEC.md par. 4) y mismo render (par. 5). Que los dos oraculos den bytes
 * identicos sobre los mismos fixtures es la prueba de que el contrato esta congelado y no
 * depende de un lenguaje. El oraculo jamas interviene en la corrida de la VM.
 *
 *   gcc -O2 -std=c11 -Wall -Wextra -o build/pong_reference oracle/pong_reference.c
 *   pong_reference step|chain|render|selftest
 *
 * Salida: LF exclusivo, sin CR y sin BOM. Entrada invalida: mensaje en stderr, exit 2 y
 * cero bytes en stdout (la salida se bufferiza completa antes de escribir).
 */
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SPEC "pong1"
#define NSPEC 5
#define NSTATE 11
#define MAX_TICK 2147483647L
#define MAX_SCORE 99
#define MAXLINE 512
#define MAXLINES 1024

typedef struct { long v[NSTATE]; } State;

static int fail(const char *why, const char *got) {
    fprintf(stderr, "entrada invalida: %s%s%s\n", why, got ? ": " : "", got ? got : "");
    return 2;
}

/* decimal con signo canonico: digitos, sin ceros a la izquierda, sin -0, sin espacios */
static int canon_int(const char *s, long *out) {
    const char *p = s;
    if (*p == '-') p++;
    if (!*p) return 0;
    for (const char *q = p; *q; q++)
        if (*q < '0' || *q > '9') return 0;
    if (*p == '0' && p[1]) return 0;
    if (s[0] == '-' && p[0] == '0' && !p[1]) return 0;
    errno = 0;
    long x = strtol(s, NULL, 10);
    if (errno) return 0;
    *out = x;
    return 1;
}

/* divide destructivamente por `sep`; los campos vacios se conservan (canon_int los rechaza) */
static int split(char *s, char sep, char **toks, int max) {
    int n = 0;
    char *p = s;
    toks[n++] = p;
    for (; *p; p++) {
        if (*p == sep) {
            *p = 0;
            if (n >= max) return -1;
            toks[n++] = p + 1;
        }
    }
    return n;
}

/* parte de estado "a,b,...,k" (11 campos, ya sin prefijo ni movimientos) */
static int parse_fields(char *fields, State *st) {
    if (strlen(fields) >= MAXLINE) return fail("seccion de estado demasiado larga", NULL);
    char *toks[16];
    int n = split(fields, ',', toks, 16);
    if (n < 0) return fail("demasiados campos de estado", NULL);
    if (n != NSTATE) return fail("se esperaban 11 campos", NULL);
    for (int k = 0; k < NSTATE; k++)
        if (!canon_int(toks[k], &st->v[k])) return fail("entero no canonico", toks[k]);
    long w = st->v[0], h = st->v[1];
    if (w < 2 || w > 64 || h < 2 || h > 64) return fail("tablero fuera de 2..64", NULL);
    if (st->v[2] < 0 || st->v[2] > w - 1 || st->v[3] < 0 || st->v[3] > h - 1)
        return fail("pelota fuera de tablero", NULL);
    if ((st->v[4] != -1 && st->v[4] != 1) || (st->v[5] != -1 && st->v[5] != 1))
        return fail("velocidades deben ser -1 o +1", NULL);
    if (st->v[6] < 0 || st->v[6] > h - 1 || st->v[7] < 0 || st->v[7] > h - 1)
        return fail("paleta fuera de filas", NULL);
    if (st->v[8] < 0 || st->v[8] > MAX_SCORE || st->v[9] < 0 || st->v[9] > MAX_SCORE)
        return fail("marcador fuera de 0..99", NULL);
    if (st->v[10] < 0 || st->v[10] > MAX_TICK) return fail("tick_index fuera de rango", NULL);
    return 0;
}

static int has_prefix(const char *line, char **rest) {
    if (strncmp(line, SPEC, NSPEC) != 0 || line[NSPEC] != ';') return 0;
    *rest = (char *)line + NSPEC + 1;
    return 1;
}

/* `pong1;<11 campos>` */
static int parse_state_line(const char *line, State *st) {
    char buf[MAXLINE];
    if (strlen(line) >= sizeof buf) return fail("linea demasiado larga", NULL);
    strcpy(buf, line);
    size_t n = strlen(buf);
    while (n && (buf[n-1] == '\n' || buf[n-1] == '\r')) buf[--n] = 0;
    char *rest;
    if (!has_prefix(buf, &rest)) return fail("prefijo 'pong1;' ausente", buf);
    if (strchr(rest, ';')) return fail("'render' no admite movimientos", rest);
    return parse_fields(rest, st);
}

/* `pong1;<11 campos>;<lm>,<rm>` */
static int parse_work_line(const char *line, State *st, long *lm, long *rm) {
    char buf[MAXLINE];
    if (strlen(line) >= sizeof buf) return fail("linea demasiado larga", NULL);
    strcpy(buf, line);
    size_t n = strlen(buf);
    while (n && (buf[n-1] == '\n' || buf[n-1] == '\r')) buf[--n] = 0;
    char *rest;
    if (!has_prefix(buf, &rest)) return fail("prefijo 'pong1;' ausente", buf);
    char *semi = strchr(rest, ';');
    if (!semi) return fail("linea de trabajo sin movimientos", buf);
    *semi = 0;
    int rc = parse_fields(rest, st);
    if (rc) return rc;
    char *mv = semi + 1;
    if (strchr(mv, ';')) return fail("demasiadas secciones", NULL);
    char *toks[4];
    int nm = split(mv, ',', toks, 4);
    if (nm != 2) return fail("se esperaban exactamente 2 movimientos", NULL);
    if (!canon_int(toks[0], lm) || !canon_int(toks[1], rm)) return fail("movimiento no canonico", NULL);
    if (*lm < -1 || *lm > 1 || *rm < -1 || *rm > 1) return fail("movimiento fuera de -1,0,+1", NULL);
    return 0;
}

static long clamp_l(long x, long lo, long hi) { return x < lo ? lo : x > hi ? hi : x; }

/* par. 4: tick, paletas, eje vertical, eje horizontal */
static int step(const State *in, long lm, long rm, State *o) {
    long w = in->v[0], h = in->v[1], bx = in->v[2], by = in->v[3];
    long vx = in->v[4], vy = in->v[5], pl = in->v[6], pr = in->v[7];
    long sl = in->v[8], sr = in->v[9], t = in->v[10];
    if (t + 1 > MAX_TICK) return fail("tick_index desbordaria 2^31-1", NULL);
    t += 1;
    pl = clamp_l(pl + lm, 0, h - 1);
    pr = clamp_l(pr + rm, 0, h - 1);
    long ny = by + vy;
    if (ny < 0 || ny > h - 1) { vy = -vy; ny = by + vy; }
    by = ny;
    long nx = bx + vx;
    int do_reset = 0, reset_dir = 0;
    if (nx < 0) {
        if (pl == by) { vx = 1; nx = 0; }
        else { sr = sr + 1 > MAX_SCORE ? MAX_SCORE : sr + 1; do_reset = 1; reset_dir = 1; }
    } else if (nx > w - 1) {
        if (pr == by) { vx = -1; nx = w - 1; }
        else { sl = sl + 1 > MAX_SCORE ? MAX_SCORE : sl + 1; do_reset = 1; reset_dir = -1; }
    }
    if (do_reset) { nx = w / 2; by = h / 2; vx = reset_dir; vy = -1; }
    o->v[0]=w; o->v[1]=h; o->v[2]=nx; o->v[3]=by; o->v[4]=vx; o->v[5]=vy;
    o->v[6]=pl; o->v[7]=pr; o->v[8]=sl; o->v[9]=sr; o->v[10]=t;
    return 0;
}

static int fmt_state(const State *s, char *out, size_t cap) {
    int n = snprintf(out, cap, SPEC ";%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld\n",
                     s->v[0], s->v[1], s->v[2], s->v[3], s->v[4], s->v[5],
                     s->v[6], s->v[7], s->v[8], s->v[9], s->v[10]);
    return n < 0 || (size_t)n >= cap ? -1 : n;
}

/* par. 5: puntos, luego paletas, luego pelota; sin marcador ni tick */
static int render_into(const State *s, char *out, size_t cap) {
    long w = s->v[0], h = s->v[1];
    size_t need = (size_t)(w * h) + (size_t)h;   /* celdas + un LF por fila */
    if (cap < need) return -1;
    char grid[64 * 64];
    for (long y = 0; y < h; y++)
        for (long x = 0; x < w; x++) grid[y * w + x] = '.';
    grid[s->v[6] * w + 0] = '|';
    grid[s->v[7] * w + (w - 1)] = '|';
    grid[s->v[3] * w + s->v[2]] = 'o';
    size_t k = 0;
    for (long y = 0; y < h; y++) {
        memcpy(out + k, grid + y * w, (size_t)w);
        k += (size_t)w;
        out[k++] = '\n';
    }
    return (int)k;
}

static int read_all_lines(char lines[MAXLINES][MAXLINE]) {
    int n = 0;
    char buf[MAXLINE];
    while (fgets(buf, sizeof buf, stdin)) {
        size_t len = strlen(buf);
        int too_long = (len == sizeof buf - 1 && buf[len - 1] != '\n');
        while (len && (buf[len-1] == '\n' || buf[len-1] == '\r')) buf[--len] = 0;
        if (too_long) return fail("linea demasiado larga", NULL);
        if (len == 0) continue;
        if (n >= MAXLINES) return fail("demasiadas lineas", NULL);
        strcpy(lines[n], buf);
        n++;
    }
    return n;
}

#define CASES 11
static const long FIX[CASES][33] = {
    {8,4,4,2, 1,-1,0,0, 0, 0,0,  0,0,  8,4,5,1, 1,-1,0,0, 0, 0,1},
    {8,4,4,0, 1,-1,0,0, 0, 0,0,  0,0,  8,4,5,1, 1, 1,0,0, 0, 0,1},
    {8,4,4,3, 1, 1,0,0, 0, 0,0,  0,0,  8,4,5,2, 1,-1,0,0, 0, 0,1},
    {8,4,0,2,-1, 1,3,0, 0, 0,0,  0,0,  8,4,0,3, 1, 1,3,0, 0, 0,1},
    {8,4,0,1,-1, 1,3,0, 0, 0,0,  0,0,  8,4,4,2, 1,-1,3,0, 0, 1,1},
    {8,4,7,1, 1, 1,0,2, 0, 0,0,  0,0,  8,4,7,2,-1, 1,0,2, 0, 0,1},
    {8,4,7,1, 1, 1,0,0, 0, 0,0,  0,0,  8,4,4,2,-1,-1,0,0, 1, 0,1},
    {8,4,7,3, 1, 1,0,0,99, 0,0,  0,0,  8,4,4,2,-1,-1,0,0,99, 0,1},
    {8,4,0,1,-1,-1,1,0, 0, 0,0, -1,0,  8,4,0,0, 1,-1,0,0, 0, 0,1},
    {8,4,4,2, 1,-1,0,3, 0, 0,0, -1,1,  8,4,5,1, 1,-1,0,3, 0, 0,1},
    {8,4,0,0,-1,-1,2,0, 0, 0,0, -1,0,  8,4,0,1, 1, 1,1,0, 0, 0,1},
};

static const char *REJECT[] = {
    "pong2;8,4,0,0,1,1,0,0,0,0,0",
    "pong1;1,1,0,0,1,1,0,0,0,0,0",
    "pong1;8,4,9,0,1,1,0,0,0,0,0",
    "pong1;8,4,0,0,0,1,0,0,0,0,0",
    "pong1;8,4,0,0,1,1,0,0,0,0,0,2147483648",
    "pong1;8,4,0,0,1,1,0,0,0,100,0",
    "pong1;8,4,0,0,1,1,0,0,0,0",
    "pong1;08,4,0,0,1,1,0,0,0,0,0",
    "pong1;-0,4,0,0,1,1,0,0,0,0,0",
    "pong1;8,4,0,0,1,1,0,0,0,0,0;2,0",
    "pong1;8,4,0,0,1,1,0,0,0,0,0;0",
    "pong1;8,4,0,0,1,1,0,0,0,0,0,0;0",
};

static int selftest(void) {
    int bad = 0;
    char out[512];
    for (int i = 0; i < CASES; i++) {
        State s = { {0} }, got;
        memcpy(s.v, FIX[i], sizeof s.v);
        if (step(&s, FIX[i][11], FIX[i][12], &got)) { bad++; fprintf(stderr, "FAIL step i=%d\n", i); continue; }
        for (int k = 0; k < NSTATE; k++) {
            if (got.v[k] != FIX[i][13 + k]) {
                bad++;
                fprintf(stderr, "FAIL caso %d campo %d: %ld != %ld\n", i, k, got.v[k], FIX[i][13 + k]);
            }
        }
        /* cada fixture debe round-trip a traves de la serializacion canonica */
        if (fmt_state(&got, out, sizeof out) < 0) { bad++; fprintf(stderr, "FAIL fmt i=%d\n", i); continue; }
        State again;
        if (parse_state_line(out, &again)) { bad++; fprintf(stderr, "FAIL round-trip i=%d: %s\n", i, out); continue; }
        for (int k = 0; k < NSTATE; k++)
            if (again.v[k] != got.v[k]) { bad++; fprintf(stderr, "FAIL round-trip campo %d i=%d\n", k, i); }
    }
    State r = { {8,4,2,2,1,-1,0,3,1,2,5} };
    const char *want_render = "|.......\n........\n..o.....\n.......|\n";
    int n = render_into(&r, out, sizeof out);
    if (n != (int)strlen(want_render) || memcmp(out, want_render, (size_t)n) != 0) {
        bad++; fprintf(stderr, "FAIL render: %.*s\n", n, out);
    }
    State b = { {8,4,0,0,1,1,0,3,0,0,0} };   /* pelota sobre paleta izquierda: gana 'o' */
    n = render_into(&b, out, sizeof out);
    if (n <= 0 || out[0] != 'o') { bad++; fprintf(stderr, "FAIL prioridad pelota\n"); }
    int nrej = (int)(sizeof REJECT / sizeof REJECT[0]), okrej = 0;
    for (int i = 0; i < nrej; i++) {
        State s; long lm, rm;
        char *rest;
        int rc = has_prefix(REJECT[i], &rest) && strchr(rest, ';')
                 ? parse_work_line(REJECT[i], &s, &lm, &rm)
                 : parse_state_line(REJECT[i], &s);
        if (rc == 0) { bad++; fprintf(stderr, "FAIL validacion acepto: %s\n", REJECT[i]); }
        else okrej++;
    }
    printf("selftest C: %d transiciones, %d rechazos, 2 renders -> %s\n",
           CASES, okrej, bad == 0 ? "PASS" : "FALLOS");
    return bad == 0 ? 0 : 1;
}

int main(int argc, char **argv) {
    static char lines[MAXLINES][MAXLINE];
    const char *mode = argc > 1 ? argv[1] : "";
    if (strcmp(mode, "selftest") == 0) return selftest();
    int n = read_all_lines(lines);
    if (n < 0) return 2;
    if (n == 0) return fail("entrada vacia", NULL);
    char buf[64 * 64 + 64 + MAXLINE];
    size_t k = 0;
    if (strcmp(mode, "step") == 0) {
        if (n != 1) return fail("'step' admite 1 linea", NULL);
        State s, out; long lm, rm;
        if (parse_work_line(lines[0], &s, &lm, &rm)) return 2;
        if (step(&s, lm, rm, &out)) return 2;
        int w = fmt_state(&out, buf, sizeof buf);
        if (w < 0) return fail("salida demasiado larga", NULL);
        fwrite(buf, 1, (size_t)w, stdout);
        return 0;
    }
    if (strcmp(mode, "chain") == 0) {
        if (n < 2) return fail("'chain' exige estado + al menos un trabajo", NULL);
        State cur, nxt;
        if (parse_state_line(lines[0], &cur)) return 2;
        for (int i = 1; i < n; i++) {
            State s; long lm, rm;
            if (parse_work_line(lines[i], &s, &lm, &rm)) return 2;
            for (int f = 0; f < NSTATE; f++)
                if (s.v[f] != cur.v[f])
                    return fail("la linea de trabajo no continua el estado actual", NULL);
            if (step(&cur, lm, rm, &nxt)) return 2;
            int w = fmt_state(&nxt, buf + k, sizeof buf - k);
            if (w < 0) return fail("salida demasiado larga", NULL);
            k += (size_t)w;
            cur = nxt;
        }
        fwrite(buf, 1, k, stdout);
        return 0;
    }
    if (strcmp(mode, "render") == 0) {
        if (n != 1) return fail("'render' admite 1 linea", NULL);
        State s;
        if (parse_state_line(lines[0], &s)) return 2;
        int w = render_into(&s, buf, sizeof buf);
        if (w < 0) return fail("frame demasiado grande", NULL);
        fwrite(buf, 1, (size_t)w, stdout);
        return 0;
    }
    fprintf(stderr, "modo desconocido: %s (step|chain|render|selftest)\n", mode);
    return 2;
}
