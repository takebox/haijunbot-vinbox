/*
 * Positive example：nocheckofpointerdereference
 * Expected：should detect possible_null_deref
 */
void foo(char *p) {
  *p = 'x'; // realrisk：nocheck
}
