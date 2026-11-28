/*
 * Expecteddetectresult: notshouldreportvulnerability
 * trap: looks likedouble free，butactualsafe
 * safepractice: useflag bit orNULLcheckpreventdouble free
 */
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

void safe_free_with_flag() {
  char *ptr = (char *)malloc(100);
  bool freed = false;

  if (ptr) {
    // useptr...
    free(ptr);
    ptr = NULL;
    freed = true;
  }

  // safe: checkflag
  if (!freed && ptr) {
    free(ptr);
    ptr = NULL;
  }
}

void safe_conditional_free(int condition) {
  char *ptr = (char *)malloc(100);
  if (!ptr)
    return;

  if (condition) {
    free(ptr);
    ptr = NULL;
  }

  // safe: ptrmaybeen setNULL
  if (ptr) {
    free(ptr);
    ptr = NULL;
  }
}
