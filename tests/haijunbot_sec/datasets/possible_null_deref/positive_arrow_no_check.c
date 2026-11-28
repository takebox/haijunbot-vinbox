/*
 * Positive example：arrow operatordereferencenonecheck
 * Expected：should detect possible_null_deref
 */
struct Foo {
  int x;
};
void bar(struct Foo *p) {
  p->x = 10; // Real risk:nocheck
}
