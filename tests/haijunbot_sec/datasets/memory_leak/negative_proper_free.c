/*
 * Negative example：correctfreememory
 * Expected：notshould detect memory_leak
 */
#include <stdlib.h>
void no_leak(int size) {
  char *buffer = (char *)malloc(size);
  if (buffer != NULL) {
    // usebuffer...
    free(buffer); // Safe:correctfreememory
  }
}
