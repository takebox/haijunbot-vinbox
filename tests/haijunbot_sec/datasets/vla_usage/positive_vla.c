/*
 * Positive example：VLAuse
 * Expected：should detect vla_usage
 */
void foo(int n) {
  char buf[n]; // Real risk:VLA
}
