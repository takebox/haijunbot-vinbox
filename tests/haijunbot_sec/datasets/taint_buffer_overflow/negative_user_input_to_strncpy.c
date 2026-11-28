// buffer overflowNegative example:usestrncpylimitlength
// should not detect：usestrncpylimitcopylength

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void safe_copy(const char *user_input) {
  char buffer[64];

  // usestrncpylimitcopylength
  strncpy(buffer, user_input, sizeof(buffer) - 1); // Safe:limit length
  buffer[sizeof(buffer) - 1] = '\0';

  printf("Copied: %s\n", buffer);
}

int main(int argc, char *argv[]) {
  if (argc > 1) {
    // taint source：command lineparameter
    safe_copy(argv[1]);
  }
  return 0;
}
