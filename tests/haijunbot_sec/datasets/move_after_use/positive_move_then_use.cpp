/*
 * Positive example：moveafteruse
 * Expected：should detect move_after_use
 */
#include <string>
#include <utility>
void foo() {
  std::string s = "hello";
  std::string t = std::move(s);
  s.size(); // Real risk:moveafteruse
}
