/*
 * Positive example：strncpynotaddterminatesymbol
 * Expected：should detect strncpy_no_nullterm
 */
#include <string.h>
void foo(char *dst, const char *src, size_t n) {
  strncpy(dst, src, n); // Real risk:terminator not added
}
