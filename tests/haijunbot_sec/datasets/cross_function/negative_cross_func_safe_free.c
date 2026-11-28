#include <stdlib.h>
#include <string.h>

char *create_buffer(void) {
  char *buf = (char *)malloc(100);
  if (buf == NULL) {
    return NULL; // check malloc return value
  }
  return buf;
}

void safe_free_buffer(char **buf) {
  if (buf != NULL && *buf != NULL) {
    free(*buf);
    *buf = NULL; // Safe:setNULL
  }
}

void use_buffer(char *buf) {
  if (buf != NULL) {
    strcpy(buf, "hello");
  }
}

int main(void) {
  char *buffer = create_buffer();
  if (buffer == NULL) {
    return 1; // checkreturnvalue
  }
  use_buffer(buffer);
  safe_free_buffer(&buffer); // safefreejuxtaposeNULL
  use_buffer(buffer);        // bufferalreadyNULL，safe
  return 0;
}
