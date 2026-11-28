/*
 * Positive example：randuse
 * Expected：should detect rand_insecure
 */
#include <stdlib.h>
void foo() {
  int x = rand(); // Real risk:notsaferandom number
}
