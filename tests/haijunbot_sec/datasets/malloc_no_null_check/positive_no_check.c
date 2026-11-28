/*
 * Positive example：mallocuncheckedNULL
 * Expected：should detect malloc_no_null_check
 */
#include <stdlib.h>
void foo() {
  char *p = malloc(100);
  p[0] = 'x'; // Real risk:uncheckedmalloc return value
}
