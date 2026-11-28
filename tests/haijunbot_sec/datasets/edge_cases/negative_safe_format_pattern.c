/*
 * Expecteddetectresult: notshouldreportvulnerability
 * trap: looks likeformat stringvulnerability，butactualsafe
 * safepractice: user inputasparameter，notis format string
 */
#include <stdio.h>
#include <string.h>

void safe_format_with_input(char *user_input) {
  char buffer[256];
  // safe: user_inputasparameter，notis format string
  snprintf(buffer, sizeof(buffer), "Message: %s", user_input);
}

void safe_printf_pattern(char *msg) {
  // safe: fixed format string
  printf("Log: %s\n", msg);
}

void safe_syslog_pattern(char *msg) {
  // safe: syslogusefixed format
  syslog(LOG_ERR, "Error occurred: %s", msg);
}
