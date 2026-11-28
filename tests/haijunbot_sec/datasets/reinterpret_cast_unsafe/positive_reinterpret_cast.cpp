/*
 * Positive example：reinterpret_castuse
 * Expected：should detect reinterpret_cast_unsafe
 */
void foo() {
  int x = 42;
  char *p = reinterpret_cast<char *>(&x); // Real risk:type cast
}
