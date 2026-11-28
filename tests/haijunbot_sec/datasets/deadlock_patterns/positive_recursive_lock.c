/*
 * Positive example：recursivelock
 * Expected：should detect deadlock_patterns
 */
#include <pthread.h>
void foo(pthread_mutex_t *m) {
  pthread_mutex_lock(m);
  pthread_mutex_lock(m); // Real risk:recursivelock
}
