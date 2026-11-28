/*
 * Positive example：mallocinusemultiplication
 * Expected：should detect alloc_size_overflow
 */
#include <stdlib.h>
void foo(size_t n, size_t m) {
  char *p = malloc(n * m); // Real risk:possible integer overflow
}
