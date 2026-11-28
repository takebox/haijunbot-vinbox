/*
 * Expected detection result: should detectinteger overflowrisk
 * vulnerability type: integer overflowcausesbufferallocatenotenough
 */
#include <stdlib.h>
#include <string.h>

void integer_overflow_vuln(int count, int size) {
  // integer overflowrisk: count * size mayoverflow
  int total = count * size;
  char *buffer = (char *)malloc(total); // mayallocatetoo small
  if (buffer) {
    memset(buffer, 0, total);
  }
}

void integer_overflow_vuln2(unsigned int len) {
  // integer overflow: len + 1 maywraparound
  char *buf = (char *)malloc(len + 1);
  if (buf) {
    memcpy(buf, "data", len); // may out of bounds write
  }
}
