/*
 * Positive example：scanf %sno width
 * Expected：should detect scanf_no_width
 */
#include <stdio.h>
void foo() {
  char buf[100];
  scanf("%s", buf); // Real risk:buffer overflow
}
