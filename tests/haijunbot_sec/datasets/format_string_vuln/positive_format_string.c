/*
 * Expected detection result: should detectformat stringvulnerability
 * vulnerability type: user inputasformat string
 */
#include <stdio.h>

void format_string_vuln(char *user_input) {
  // format stringvulnerability: user_input maycontain %n %s etc
  printf(user_input);          // dangerous!
  fprintf(stderr, user_input); // dangerous!
}

void format_string_vuln2(char *user_input) {
  char buffer[256];
  // format stringvulnerability
  sprintf(buffer, user_input); // dangerous!
}
