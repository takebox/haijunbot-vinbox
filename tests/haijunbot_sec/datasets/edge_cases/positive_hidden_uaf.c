/*
 * Expected detection result: should detectUAFvulnerability
 * trap: looks like hasNULLcheck，butcheckinfreebefore，notaffectsubsequentuse
 * vulnerability type: hiddenofuse after free
 */
#include <stdlib.h>
#include <string.h>

void hidden_uaf_vuln(char *input) {
  char *buffer = (char *)malloc(100);
  if (buffer == NULL)
    return; // looks safe

  strcpy(buffer, input);
  free(buffer);

  // trap: not set hereNULL，subsequentcodemaymisuse
  if (buffer != NULL) {       // this check always true！
    printf("Buffer freed\n"); // buffer still points to freed memory
  }

  // more hidden: passanother variable
  char *ptr = buffer; // ptr now also points to freed memory
  if (ptr != NULL) {
    strcpy(ptr, "test"); // UAF!
  }
}
