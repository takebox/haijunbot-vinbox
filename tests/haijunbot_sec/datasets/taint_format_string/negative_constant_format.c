// format stringvulnerabilityNegative example:constant format string
// should not detect：useconstant format string

#include <stdio.h>
#include <stdlib.h>

void safe_printf(char *user_input) {
  // taint sink：useconstant format string
  printf("User input: %s\n", user_input); // Safe:constant format
}

int main(int argc, char *argv[]) {
  if (argc > 1) {
    // taint source：command lineparameter
    safe_printf(argv[1]);
  }
  return 0;
}
