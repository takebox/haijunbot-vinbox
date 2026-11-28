/*
 * Negative example：reallocusetemp variable receives andcheckNULL
 * Expected：notshould detect realloc_assign_back
 */
#include <stdlib.h>
void foo() {
  char *p = malloc(100);
  char *tmp = realloc(p, 200); // Safe:usetemp variable
  if (tmp != NULL) {
    p = tmp; // only on successassign
  } else {
    // on failurepstill valid，can continueuseorfree
    free(p);
  }
}
