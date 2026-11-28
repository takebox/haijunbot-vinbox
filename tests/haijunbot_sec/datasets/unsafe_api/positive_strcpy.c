/*
 * Positive example：strcpyuse
 * Expected：should detect unsafe_api (strcpy)
 */
#include <string.h>
void foo(char *dst, const char *src) {
  strcpy(dst, src); // Real risk:maybuffer overflow
}
