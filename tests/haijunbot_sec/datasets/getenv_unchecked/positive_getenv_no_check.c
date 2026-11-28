/*
 * Positive example：getenvreturnvalueunchecked
 * Expected：should detect getenv_unchecked
 */
#include <stdio.h>
#include <stdlib.h>
void foo() {
  char *home = getenv("HOME");
  printf("%s\n", home); // Real risk:uncheckedreturnvalue
}
