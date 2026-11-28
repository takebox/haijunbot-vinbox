/*
 * Expecteddetectresult: notshouldreportvulnerability
 * trap: looks likeinteger overflow，butactualhas completecheck
 * safepractice: completeinteger overflowcheck
 */
#include <limits.h>
#include <stdlib.h>

void complete_overflow_check(unsigned int count, unsigned int size) {
  // safe: completeoverflowcheck
  if (count > 0 && size > 0 && count <= UINT_MAX / size) {
    unsigned int total = count * size;
    char *buf = (char *)malloc(total);
    if (buf)
      free(buf);
  }
}

void safe_signed_check(int len) {
  // safe: checkadditionoverflow
  if (len > 0 && len < INT_MAX - 100) {
    int size = len + 100;
    char *buf = (char *)malloc(size);
    if (buf)
      free(buf);
  }
}

void safe_multiplication(int a, int b) {
  // safe: checkmultiplication overflow
  if (a > 0 && b > 0 && a <= INT_MAX / b) {
    int result = a * b;
    char *buf = (char *)malloc(result);
    if (buf)
      free(buf);
  }
}
