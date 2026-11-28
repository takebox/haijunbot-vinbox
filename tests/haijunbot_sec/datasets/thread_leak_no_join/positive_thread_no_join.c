/*
 * Positive example：threadcreateafter notjoin
 * Expected：should detect thread_leak_no_join
 */
#include <pthread.h>
void foo() {
  pthread_t t;
  pthread_create(&t, NULL, NULL, NULL); // Real risk:notjoin
}
