/*
 * Expecteddetectresult: notshouldreportvulnerability
 * safepractice: usesafeofintegeroperationcheck
 */
#include <limits.h>
#include <stdlib.h>

void safe_integer_alloc(int count, int size) {
  // safe: checkinteger overflow
  if (count > 0 && size > 0 && count <= INT_MAX / size) {
    int total = count * size;
    char *buffer = (char *)malloc(total);
    if (buffer) {
      memset(buffer, 0, total);
      free(buffer);
    }
  }
}
