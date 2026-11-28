/*
 * Positive example：const_castremoveconst
 * Expected：should detect const_cast_unsafe
 */
void foo(const int *p) {
  int *q = const_cast<int *>(p);
  *q = 100; // realrisk：removeconst
}
