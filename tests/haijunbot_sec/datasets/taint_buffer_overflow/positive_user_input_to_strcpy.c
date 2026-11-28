// buffer overflowPositive example:user input -> strcpy taint propagation
// should detect：user inputcopyto fixedsizebuffer

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void vulnerable_copy(const char *user_input) {
  char buffer[64];

  // taint sink：user inputcopyto fixedsizebuffer
  // taint propagationpath：argv -> user_input -> strcpy -> buffer
  strcpy(buffer, user_input); // buffer overflowrisk

  printf("Copied: %s\n", buffer);
}

int main(int argc, char *argv[]) {
  if (argc > 1) {
    // taint source：command lineparameter
    vulnerable_copy(argv[1]);
  }
  return 0;
}
