/*
 * Negative example：vectorhas accesscheck
 * Expected：notshould detect vector_string_bounds_check
 */
#include <vector>
void foo() {
  std::vector<int> v;
  if (!v.empty()) {
    v[0] = 42; // Safe:hascheck
  }
}
