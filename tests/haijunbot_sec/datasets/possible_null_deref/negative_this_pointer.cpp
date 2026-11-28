/*
 * Negative example：C++ this pointer
 * Expected：notshould detect possible_null_deref
 */
class Foo {
  int x;
  void bar() {
    this->x = 10; // safe：this pointer
  }
};
