/*
 * Negative example：fopenreturnvalue alreadycheck
 * Expected：notshould detect unchecked_io
 */
#include <stdio.h>
void foo() {
  FILE *fp = fopen("test.txt", "r");
  if (fp == NULL)
    return;
  char buf[100];
  size_t n = fread(buf, 1, 100, fp); // Safe:hascheck
  if (n < 100) {
    // handlereadnotcomplete case
  }
}
