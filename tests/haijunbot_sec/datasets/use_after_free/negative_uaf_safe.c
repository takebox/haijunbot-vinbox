/*
 * Expecteddetectresult: notshouldreportvulnerability
 * safepractice: freepost-placeNULL，subsequentusebeforecheck
 */
#include <stdlib.h>
#include <string.h>

void safe_free_pattern() {
  char *ptr = (char *)malloc(100);
  if (ptr == NULL)
    return;
  strcpy(ptr, "hello");
  free(ptr);
  ptr = NULL; // safe: setNULL

  // safe: usebeforecheck
  if (ptr != NULL) {
    printf("%s\n", ptr);
  }
}
