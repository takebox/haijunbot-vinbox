/*
 * Positive example：strtokuse
 * Expected：should detect strtok_nonreentrant
 */
#include <string.h>
void foo(char *s) {
  char *token = strtok(s, ","); // Real risk:non-reentrant
}
