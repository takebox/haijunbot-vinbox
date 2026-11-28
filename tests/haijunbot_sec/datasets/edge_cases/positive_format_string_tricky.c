/*
 * Expected detection result: should detectformat stringvulnerability
 * trap: looks like format string，butuser inputstill in format position
 * vulnerability type: hiddenofformat stringvulnerability
 */
#include <stdio.h>
#include <string.h>

void tricky_format_string(char *user_input) {
  char buffer[256];
  // trap: looks like has"%s"，butuser_inputin format string position
  snprintf(buffer, sizeof(buffer), user_input); // dangerous!
}

void format_with_concat(char *user_input) {
  char fmt[100];
  // trap: constructed format string containsuser input
  snprintf(fmt, sizeof(fmt), "Error: %s", user_input);
  printf(fmt); // ifuser_inputcontain%format specifier，dangerous!
}

void syslog_format_vuln(char *msg) {
  // trap: syslogformat stringparameter
  syslog(LOG_ERR, msg); // dangerous!
}
