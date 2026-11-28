/*
 * Positive example：popencall
 * Expected：should detect command_execution
 */
#include <stdio.h>
void foo(char *cmd) {
  FILE *fp = popen(cmd, "r"); // Real risk:command injection
}
