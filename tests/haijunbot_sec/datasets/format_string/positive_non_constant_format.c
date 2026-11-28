/*
 * Positive example：non-constantformat string
 * Expected：should detect format_string
 */
#include <stdio.h>
void foo(char *fmt) {
  printf(fmt); // Real risk:format stringvulnerability
}
