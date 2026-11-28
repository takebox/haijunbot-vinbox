/*
 * Negative example (bypass)：execl firstparameterfirstassignforliteralpath，after byoverride tousercontrollablevalue
 * Expected: detector should detect, but _var_assigned_literal finds literal assign and considers safe, unchecked override
 * vulnerability: path overridden by external input passed to execl, can execute arbitrary program
 */
#include <unistd.h>

char *user_ctrl = "/bin/ls";  // global literal, used to make detector think user_ctrl safe

void vulnerable(user_ctrl)
char *user_ctrl;
{
    char *path = "/bin/ls";       // literal assign (detector thinks safe)
    path = user_ctrl;            // overridden to user-controlled path
    execl(path, "arg1", NULL);   // Real risk:executearbitrary program
}
