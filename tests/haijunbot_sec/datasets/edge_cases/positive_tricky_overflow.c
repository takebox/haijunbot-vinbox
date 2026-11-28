/*
 * Expected detection result: should detectinteger overflow
 * trap: looks like hascheck，butchecknotcomplete
 * vulnerability type: notcompleteinteger overflowcheck
 */
#include <limits.h>
#include <stdlib.h>

void incomplete_overflow_check(unsigned int count, unsigned int size) {
  // trap: onlycheckdonecount，nocheckmultiplication overflow
  if (count > 0 && size > 0) {         // looks like hascheck
    unsigned int total = count * size; // may still overflow!
    char *buf = (char *)malloc(total);
    if (buf)
      free(buf);
  }
}

void signed_overflow_trap(int len) {
  // trap: lenwhen negative，len + 100maybecomes very small number
  if (len > 0) {          // looks likecheckdone
    int size = len + 100; // iflenclose toINT_MAX，will overflow
    char *buf = (char *)malloc(size);
    if (buf)
      free(buf);
  }
}

void multiplication_overflow(int a, int b) {
  // trap: looks likesafe，buta*bmayoverflow
  if (a > 0 && b > 0) {
    int result = a * b; // may overflow
    char *buf = (char *)malloc(result);
    if (buf)
      free(buf);
  }
}
