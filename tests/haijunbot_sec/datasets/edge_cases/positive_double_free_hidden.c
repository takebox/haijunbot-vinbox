/*
 * Expected detection result: should detectdouble free
 * trap: looks like hascheck，butcheckinvalid
 * vulnerability type: hiddenofdouble free
 */
#include <stdlib.h>
#include <string.h>

void hidden_double_free(char *input) {
  char *ptr = (char *)malloc(100);
  if (!ptr)
    return;

  strcpy(ptr, input);
  free(ptr);

  // trap: conditionmaytrue，causesdouble free
  if (strlen(input) > 0) {
    free(ptr); // double free!
  }
}

void double_free_via_alias() {
  char *a = (char *)malloc(50);
  char *b = a; // bisaalias

  free(a);
  // trap: looks likefreeisb，actualis same memory block
  free(b); // double free!
}
