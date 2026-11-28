/*
 * Negative example：usesafeofstrncpy
 * Expected：notshould detect buffer_overflow
 */
#include <string.h>
void safe_copy(const char *input) {
  char buffer[100];
  strncpy(buffer, input, sizeof(buffer) - 1);
  buffer[sizeof(buffer) - 1] = '\0'; // Safe:limited length and manually add terminator
}
