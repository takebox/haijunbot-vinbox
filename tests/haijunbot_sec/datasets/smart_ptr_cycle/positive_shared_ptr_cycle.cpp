/*
 * Positive example：shared_ptrcycle reference
 * Expected：should detect smart_ptr_cycle
 */
#include <memory>
class A {
  std::shared_ptr<A> next;
};
void foo() {
  auto a = std::make_shared<A>();
  a->next = a; // Real risk:cycle reference
}
