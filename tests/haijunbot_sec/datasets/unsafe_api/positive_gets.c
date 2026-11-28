/*
 * Positive example：getsuse
 * Expected：should detect unsafe_api (gets)
 */
#include <stdio.h>
void foo() {
  char buf[100];
  gets(buf); // Real risk:extremedangerous
}
