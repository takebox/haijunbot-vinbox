/*
 * Positive example：allocausevariablesize
 * Expected：should detect alloca_unbounded
 */
#include <alloca.h>
void foo(size_t n) {
  char *p = alloca(n); // Real risk:unbounded allocation
}
