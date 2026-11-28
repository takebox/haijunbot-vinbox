/*
 * Expected detection result: should detect buffer overflow risk
 * Trap: appears to use strncpy, but length parameter is wrong
 * vulnerability type: incorrectly used "safe" function
 */
#include <stdlib.h>
#include <string.h>

void strncpy_wrong_size(char *input) {
  char buffer[50];
  // Trap: sizeof(input) is pointer size, not buffer size!
  strncpy(buffer, input, sizeof(input)); // only copies 4 or 8 bytes
  buffer[sizeof(buffer) - 1] = '\0';
}

void strncpy_off_by_one(char *input) {
  char buffer[100];
  // Trap: looks safe, but if input is long, may truncate but not terminate
  strncpy(buffer, input, 100); // may not terminate
                               // no manually added terminator!
}

void memcpy_size_confusion(char *src, size_t len) {
  char *dst = (char *)malloc(50);
  // Trap: len may be greater than 50
  if (dst) {
    memcpy(dst, src, len); // may overflow!
    free(dst);
  }
}
