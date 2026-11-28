/*
 * Negative example：getenvreturnvalue alreadycheck
 * Expected：notshould detect getenv_unchecked
 */
#include <stdio.h>
#include <stdlib.h>
void foo() {
  char *home = getenv("HOME");
  if (home == NULL)
    return;
  printf("%s\n", home); // Safe:hascheck
}
