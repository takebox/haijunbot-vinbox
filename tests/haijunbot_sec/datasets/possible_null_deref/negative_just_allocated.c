/*
 * Negative example：allocateafter hasNULLcheckagainuse
 * Expected：notshould detect possible_null_deref
 */
#include <stdlib.h>
void foo() {
  char *p = malloc(100);
  if (p == NULL) return;
  p[0] = 'x'; // Safe:alreadycheckNULL
}
