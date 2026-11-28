/*
 * Positive example：uninitialized pointeruse
 * Expected：should detect uninitialized_ptr_use
 */
void foo() {
  char *p;
  *p = 'x'; // realrisk：uninitialized
}
