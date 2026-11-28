/*
 * Positive example：mktempuse
 * Expected：should detect insecure_tmpfile
 */
#include <stdlib.h>
void foo() {
  char template[] = "fileXXXXXX";
  mktemp(template); // Real risk:notsafetemporary file
}
