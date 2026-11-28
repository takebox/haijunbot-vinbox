/*
 * Expecteddetectresult: notshouldreportvulnerability
 * trap: looks likedangerous，butactualsafe
 * safepractice: correctusestringfunction
 */
#include <stdlib.h>
#include <string.h>

void actually_safe_strncpy(char *input) {
  char buffer[100];
  // safe: correctusesizeof(buffer) - 1
  strncpy(buffer, input, sizeof(buffer) - 1);
  buffer[sizeof(buffer) - 1] = '\0'; // ensure termination
}

void safe_memcpy_with_check(char *src, size_t len) {
  char *dst = (char *)malloc(100);
  // safe: checklength
  if (dst && len < 100) {
    memcpy(dst, src, len);
    dst[len] = '\0';
    free(dst);
  } else if (dst) {
    free(dst);
  }
}

void safe_snprintf(char *input) {
  char buffer[256];
  // safe: usesnprintfand specifiedcorrectsize
  snprintf(buffer, sizeof(buffer), "Input: %s", input);
}
