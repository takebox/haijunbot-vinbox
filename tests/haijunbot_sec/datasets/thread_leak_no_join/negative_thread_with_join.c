/*
 * Negative example：threadcreateafter hasjoin
 * Expected：notshould detect thread_leak_no_join
 */
#include <pthread.h>
void foo() {
  pthread_t t;
  pthread_create(&t, NULL, NULL, NULL);
  pthread_join(t, NULL); // Safe:hasjoin
}
