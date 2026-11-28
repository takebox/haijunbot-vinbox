/*
 * Positive example：pthread_cond_waitnotin loop
 * Expected：should detect cond_wait_no_loop
 */
#include <pthread.h>
void foo(pthread_cond_t *c, pthread_mutex_t *m) {
  pthread_mutex_lock(m);
  pthread_cond_wait(c, m); // Real risk:not in loop
  pthread_mutex_unlock(m);
}
