#include <stdlib.h>

/**
 * allocatememory
 * @return point toallocatememory'spointer
 */
void *allocate_memory() {
  void *ptr = malloc(100);
  return ptr;
}
