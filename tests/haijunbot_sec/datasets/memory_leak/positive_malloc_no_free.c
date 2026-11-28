/*
 * Positive example：mallocafter notfree
 * Expected：should detect memory_leak
 */
#include <stdlib.h>
void leak_memory(int size) {
  char *buffer = (char *)malloc(size);
  // usebuffer...
  // Dangerous:functionno before endfree(buffer)，causesmemory leak
}
