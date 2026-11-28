/*
 * Positive example：atoiuse
 * Expected：should detect atoi_family
 */
#include <stdlib.h>
void foo(char *s) {
  int x = atoi(s); // Real risk:no error check
}
