// Double FreeNegative example:correctfreeonce
// should not detect：memory onlyfreeonce

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char *argv[]) {
  // allocatememory
  char *buffer = (char *)malloc(256);
  if (buffer == NULL) {
    return 1;
  }

  // usememory
  strcpy(buffer, "Hello, World!");
  printf("Buffer: %s\n", buffer);

  // correct：onlyfreeonce
  free(buffer);

  // set toNULLprevent danglingnull pointer
  buffer = NULL;

  return 0;
}
