/*
 * Positive example：freeafteruse
 * Expected：should detect uaf_suspect
 */
#include <stdlib.h>
void foo() {
  char *p = malloc(100);
  free(p);
  p[0] = 'x'; // Real risk:UAF
}
