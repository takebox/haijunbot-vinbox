/*
 * Negative example (bypass)：format stringstored instruct fieldin，firstassignforliteraloverride again
 * Expected: detector should detect, but_var_assigned_literallook back findliteralassignimmediately thinkssafe
 * vulnerability：cfg->format mayisusercontrollableofformat string
 */
#include <stdio.h>

typedef struct {
    char *format;
} Config;

void vulnerable(Config *cfg) {
    if (cfg == NULL) return;
    char *fmt = "%d";        // literal assign (detector thinks safe)
    fmt = cfg->format;        // overridden to user-controlled value
    printf(fmt);              // Real risk:fmt now is user-controllable format string
}
