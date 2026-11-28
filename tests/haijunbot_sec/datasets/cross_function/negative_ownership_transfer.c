#include <stdlib.h>

int *create_data(void) {
  int *data = (int *)malloc(sizeof(int) * 10);
  if (data == NULL) {
    return NULL; // check malloc return value
  }
  return data; // ownership transfergivecallperson
}

void process_and_free(int *data) {
  if (data == NULL) {
    return; // checkNULL
  }
  // handledata
  for (int i = 0; i < 10; i++) {
    data[i] = i * 2;
  }
  free(data); // correct：function responsiblefree
}

int main(void) {
  int *d = create_data();
  if (d == NULL) {
    return 1; // checkreturnvalue
  }
  process_and_free(d); // ownership transfer，correctfree
  // dnotvalid again，but notuse
  return 0;
}
