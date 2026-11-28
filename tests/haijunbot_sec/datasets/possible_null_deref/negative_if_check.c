/*
 * Negative example：hasifstatementcheck
 * Expected：notshould detect possible_null_deref
 */
void foo(char *p) {
  if (p != NULL) {
    *p = 'x'; // Safe:hascheck
  }
}
