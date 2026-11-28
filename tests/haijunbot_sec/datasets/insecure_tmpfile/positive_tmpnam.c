/*
 * Positive example：tmpnamuse
 * Expected：should detect insecure_tmpfile
 */
#include <stdio.h>
void foo() {
  char name[L_tmpnam];
  tmpnam(name); // Real risk:notsafetemporary file
}
