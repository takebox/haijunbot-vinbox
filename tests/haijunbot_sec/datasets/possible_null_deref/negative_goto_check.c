/*
 * Negative example：hasgotoerrorhandle
 * Expected：notshould detect possible_null_deref
 */
void foo(char *p) {
  if (!p)
    goto error;
  *p = 'x'; // Safe:hasgotodefense
error:
  return;
}
