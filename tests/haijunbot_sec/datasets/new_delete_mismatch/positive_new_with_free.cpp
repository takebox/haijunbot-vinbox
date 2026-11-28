/*
 * Positive example：newconfigfree
 * Expected：should detect new_delete_mismatch
 */
void foo() {
  int *p = new int(42);
  free(p); // Real risk:new/deletenot match
}
