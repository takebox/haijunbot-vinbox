/*
 * Positive example：systemcall
 * Expected：should detect command_execution
 */
#include <stdlib.h>
void foo(char *cmd) {
  system(cmd); // Real risk:command injection
}
