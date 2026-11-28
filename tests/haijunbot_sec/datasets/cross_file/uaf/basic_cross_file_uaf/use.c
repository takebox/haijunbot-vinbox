#include <stddef.h>

/**
 * usememory
 * @param ptr points to memorypointer
 */
void use_memory(void *ptr) {
  if (ptr != NULL) {
    // useperform some operations on memory
    char *data = (char *)ptr;
    data[0] = 'A';
  }
}
