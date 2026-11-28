/*
 * Positive example：fopenreturnvalueunchecked
 * Expected：should detect unchecked_io
 */
#include <stdio.h>
void foo() {
  FILE *fp = fopen("test.txt", "r");
  char buf[100];
  fread(buf, 1, 100, fp); // Real risk:uncheckedfopenreturnvalue
}
