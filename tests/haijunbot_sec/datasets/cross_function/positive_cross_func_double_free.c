#include <stdlib.h>

void allocate_and_free(int **ptr, int should_free) {
  *ptr = (int *)malloc(sizeof(int));
  if (should_free) {
    free(*ptr);
    // freenot set afterNULL
  }
}

void process_ptr(int *ptr) {
  // mayagainfree
  free(ptr); // Double Freerisk
}

int main(void) {
  int *data = NULL;
  allocate_and_free(&data, 1); // internally alreadyfree
  process_ptr(data);           // againfree -> Double Free
  return 0;
}
