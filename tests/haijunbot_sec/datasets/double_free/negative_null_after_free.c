/*
 * Negative example：freepost-placeNULL
 * Expected：notshould detect double_free
 */
#include <stdlib.h>
void safe_free_example(char *ptr) {
  free(ptr);
  ptr = NULL; // Safe:freeimmediately set afterNULL
  // even if againfree(ptr)alsosafeof（free(NULL)is legitimate）
}
