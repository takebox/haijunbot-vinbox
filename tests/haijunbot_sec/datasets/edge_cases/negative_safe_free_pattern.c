/*
 * Expecteddetectresult: notshouldreportvulnerability
 * trap: looks likeUAF，butactualissafeof
 * safepractice: freeimmediately set afterNULL，subsequentcheckvalid
 */
#include <stdlib.h>
#include <string.h>

void safe_free_with_null() {
  char *buffer = (char *)malloc(100);
  if (buffer == NULL)
    return;

  strcpy(buffer, "data");
  free(buffer);
  buffer = NULL; // key: immediately setNULL

  // safe: bufferforNULL，notwillexecute
  if (buffer != NULL) {
    printf("%s\n", buffer); // will notexecute
  }

  // safe: strcpycheckNULL
  if (buffer) {
    strcpy(buffer, "test"); // will notexecute
  }
}

void safe_free_early_return() {
  char *ptr = (char *)malloc(50);
  if (!ptr)
    return;

  // useptr
  memset(ptr, 0, 50);

  free(ptr);
  ptr = NULL;
  return; // advancereturn，subsequent code will notexecute

  // dead code，notwillexecute
  strcpy(ptr, "dead");
}
