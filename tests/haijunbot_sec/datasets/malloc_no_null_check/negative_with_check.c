/*
 * Negative example：mallochascheck
 * Expected：notshould detect malloc_no_null_check
 */
#include <stdlib.h>
void foo() {
  char *p = malloc(100);
  if (p == NULL)
    return;
  p[0] = 'x'; // Safe:hascheck
}
