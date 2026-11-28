/*
 * Positive example：get()resultstored
 * Expected：should detect smart_ptr_get_unsafe
 */
#include <memory>
void foo() {
  auto p = std::make_shared<int>(42);
  int *raw = p.get();
  *raw = 100; // realrisk：barepointerstore
}
