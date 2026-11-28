/*
 * Positive example：freeafterpassgivefunction
 * Expected：should detect uaf_suspect
 */
#include <stdio.h>
#include <stdlib.h>
void foo() {
  char *p = malloc(100);
  free(p);
  printf("%p\n", p); // Real risk:UAF
}
