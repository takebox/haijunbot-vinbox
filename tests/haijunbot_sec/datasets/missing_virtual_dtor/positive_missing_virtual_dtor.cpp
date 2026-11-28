/*
 * Positive example：base class missingvirtual destructor
 * Expected：should detect missing_virtual_dtor
 */
class Base {
public:
  virtual void foo() {} // virtual function，but destructor not virtual
  ~Base() {}
};
class Derived : public Base {
public:
  ~Derived() {}
};
void bar() {
  Base *b = new Derived();
  delete b; // Real risk:missingvirtual destructor
}
