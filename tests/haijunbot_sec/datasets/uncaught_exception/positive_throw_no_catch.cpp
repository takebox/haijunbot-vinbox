/*
 * Positive example：thrownonecatch
 * Expected：should detect uncaught_exception
 */
void foo() {
  throw 42; // Real risk:uncaughtexception
}
