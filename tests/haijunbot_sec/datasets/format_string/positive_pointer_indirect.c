/*
 * Negative example (bypass)：variable firstassignforliteral，after byoverride tousercontrollablevalue
 * Expected: detector should detect, butheuristic only checks existenceliteralassignandnotcheckoverride
 * vulnerability：fmt byassignforexternalparameter（usercontrollable），printf(fmt) triggerformat stringvulnerability
 */
#include <stdio.h>

void vulnerable(const char *user_input) {
    char *fmt = "%d";            // the1timesassign：literal（detector sees this and thinkssafe）
    fmt = (char *)user_input;     // overridden to externalinput
    printf(fmt);                  // Real risk:fmt now is user-controllable format string
}
