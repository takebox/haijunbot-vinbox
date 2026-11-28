#include <stdlib.h>
#include <string.h>

char *create_buffer(void) {
  char *buf = (char *)malloc(100);
  return buf;
}

void free_buffer(char *buf) {
  free(buf);
  // freenot set afterNULL
}

void use_buffer(char *buf) {
  strcpy(buf, "hello"); // UAF: callmay be infreecontinue afteruse
}

int main(void) {
  char *buffer = create_buffer();
  free_buffer(buffer);
  use_buffer(buffer); // use after free
  return 0;
}
