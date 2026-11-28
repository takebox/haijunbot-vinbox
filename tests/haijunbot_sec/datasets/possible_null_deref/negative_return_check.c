/*
 * Negative example：hasreturndefense
 * Expected：notshould detect possible_null_deref
 */
void foo(char *p) {
  if (!p)
    return;
  *p = 'x'; // Safe:hasreturndefense
}
