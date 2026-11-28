/*
 * Positive example：localtimefunctionuse
 * Expected：should detect time_apis_not_threadsafe
 */
#include <time.h>
void foo() {
  time_t t = time(NULL);
  struct tm *tm = localtime(&t); // Real risk:notthreadsafe
}
