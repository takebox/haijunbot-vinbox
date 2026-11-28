// format stringvulnerabilityPositive example:user input -> printf taint propagation
// should detect：user inputdirectused asformat string

#include <stdio.h>
#include <stdlib.h>

void vulnerable_printf(char *user_input) {
  // taint sink：user inputused asformat string
  // taint propagationpath：argv -> user_input -> printf
  printf(user_input); // format stringvulnerability
}

int main(int argc, char *argv[]) {
  if (argc > 1) {
    // taint source：command lineparameter
    vulnerable_printf(argv[1]);
  }
  return 0;
}
