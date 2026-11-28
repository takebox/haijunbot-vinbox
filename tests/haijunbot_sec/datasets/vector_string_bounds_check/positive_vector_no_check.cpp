/*
 * Positive example：vectorno accesscheck
 * Expected：should detect vector_string_bounds_check
 */
#include <vector>
void foo() {
  std::vector<int> v;
  v[0] = 42; // Real risk:nonebounds check
}
