/*
 * cross-file format string - log output module
 * user input in this file used as format string
 * Missed detection: c_checker's _rule_format_string doesn't cover format string parameters of syslog/err functions
 */
#include <stdio.h>
#include <syslog.h>
#include <err.h>

/* use syslog output - missed detection: syslog format string not covered */
void log_message(const char *fmt) {
    syslog(LOG_ERR, fmt);  /* fmt from user input, format string injection */
}

/* use printf output */
void print_formatted(const char *fmt, int value) {
    printf(fmt, value);  /* fmt from user input, format string injection */
}

/* use err output - missed detection: err format string not covered */
void fatal_error(const char *fmt) {
    err(1, fmt);  /* fmt from user input, format string injection */
}
