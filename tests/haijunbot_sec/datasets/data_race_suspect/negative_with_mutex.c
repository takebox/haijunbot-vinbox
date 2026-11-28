/*
 * Negative example：hasmutexprotect
 * Expected：notshould detect data_race_suspect
 */
#include <pthread.h>
int shared_data = 0;
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
void *thread_func(void *arg) {
  pthread_mutex_lock(&mutex);
  shared_data = 100; // Safe:haslockprotect
  pthread_mutex_unlock(&mutex);
  return NULL;
}
int main() {
  pthread_t t;
  pthread_create(&t, NULL, thread_func, NULL);
  pthread_join(t, NULL);
  return 0;
}
