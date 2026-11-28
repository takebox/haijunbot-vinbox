/*
 * Negative example：whileloop conditioncheck
 * Expected：notshould detect possible_null_deref
 */
void foo(char *p) {
  while (p && *p) {
    p++; // Safe:whileconditioncheck
  }
}
