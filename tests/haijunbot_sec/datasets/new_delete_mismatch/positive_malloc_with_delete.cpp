/*
 * Positive example：mallocconfigdelete
 * Expected：should detect new_delete_mismatch
 */
#include <stdlib.h>
void foo() {
  int *p = (int *)malloc(sizeof(int));
  delete p; // Real risk:new/deletenot match
}
