/*
 * Positive example：sprintfuse
 * Expected：should detect unsafe_api (sprintf)
 */
#include <stdio.h>
void foo(char *buf) {
  sprintf(buf, "%s", "hello"); // Real risk:maybuffer overflow
}
