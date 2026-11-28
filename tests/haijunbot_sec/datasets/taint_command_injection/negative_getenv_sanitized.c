// command injectionNegative example:getenv -> system has sanitization
// should not detect：environment variable data sanitized and used forexecutesystem command

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// sanitizefunction：removedangerouschar
void sanitize_command(char *cmd) {
  char *dangerous_chars = ";&|`$\"";
  char *p = cmd;
  while (*p) {
    if (strchr(dangerous_chars, *p)) {
      *p = ' '; // replace with space
    }
    p++;
  }
}

int main(int argc, char *argv[]) {
  // taint source：get data from environment variable
  char *cmd = getenv("CMD");

  if (cmd != NULL) {
    // sanitize：removedangerouschar
    sanitize_command(cmd);

    // taint sink：executesystem command（sanitized）
    system(cmd); // Safe:sanitized
  }

  return 0;
}
