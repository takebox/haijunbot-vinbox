/*
 * Negative example：pthread_cond_waitin loop
 * Expected：notshould detect cond_wait_no_loop
 */
#include <pthread.h>
int condition = 0;
void foo(pthread_cond_t *c, pthread_mutex_t *m) {
  pthread_mutex_lock(m);
  while (!condition) {
    pthread_cond_wait(c, m); // Safe:in loop
  }
  pthread_mutex_unlock(m);
}
