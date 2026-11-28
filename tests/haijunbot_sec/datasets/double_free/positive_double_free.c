/*
 * Positive example：repeatfreememory
 * Expected：should detect double_free
 */
#include <stdlib.h>
void double_free_example(char *ptr) {
  free(ptr);
  // ... some code ...
  free(ptr); // Dangerous:repeatfreesame memory block
}
