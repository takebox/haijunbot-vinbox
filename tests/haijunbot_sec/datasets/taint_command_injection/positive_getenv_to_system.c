// command injectionPositive example:getenv -> system taint propagation
// should detect：environment variable datadirectused forexecutesystem command

#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
  // taint source：get data from environment variable
  char *cmd = getenv("CMD");

  if (cmd != NULL) {
    // taint sink：executesystem command
    // taint propagationpath：getenv -> cmd -> system
    system(cmd); // command injectionrisk
  }

  return 0;
}
