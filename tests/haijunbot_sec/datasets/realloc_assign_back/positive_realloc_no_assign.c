/*
 * Positive example：reallocnot assigned back to originalpointer
 * Expected：should detect realloc_assign_back
 */
#include <stdlib.h>
void foo() {
  char *p = malloc(100);
  realloc(p, 200); // Real risk:not assigned back
}
