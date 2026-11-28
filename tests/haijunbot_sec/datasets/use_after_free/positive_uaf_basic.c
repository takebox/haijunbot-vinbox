/*
 * Expected detection result: should detect use_after_free vulnerability
 * vulnerability type: use after free (UAF)
 * description: freecontinue afterusepointer
 */
#include <stdlib.h>
#include <string.h>

void use_after_free_basic() {
  char *ptr = (char *)malloc(100);
  strcpy(ptr, "hello");
  free(ptr);
  // freecontinue afteruse - severevulnerability
  printf("%s\n", ptr);  // UAF: readalreadyfreememory
  strcpy(ptr, "world"); // UAF: writealreadyfreememory
}
