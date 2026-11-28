/*
 * Expecteddetectresult: notshouldreportvulnerability
 * safepractice: usefixedformat string
 */
#include <stdio.h>

void safe_format_string(char *user_input) {
  // safe: usefixedformat string
  printf("%s", user_input);
  fprintf(stderr, "Error: %s", user_input);
}

void safe_format_string2(char *user_input) {
  char buffer[256];
  // safe: usefixedformat string
  snprintf(buffer, sizeof(buffer), "Message: %s", user_input);
}
