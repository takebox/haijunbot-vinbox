#include <stdlib.h>

void maybe_free(int **ptr, int condition) {
  if (ptr == NULL || *ptr == NULL) {
    return; // checkNULL
  }
  if (condition) {
    free(*ptr);
    *ptr = NULL;
  }
}

int main(void) {
  int *data = (int *)malloc(sizeof(int));
  if (data == NULL) {
    return 1; // check malloc return value
  }
  *data = 42;

  maybe_free(&data, 1); // conditionfree

  if (data == NULL) {
    // correct：checkafteruse
    return 0;
  }

  *data = 100; // onlydatanotforNULLonly whenexecute
  free(data);
  return 0;
}
