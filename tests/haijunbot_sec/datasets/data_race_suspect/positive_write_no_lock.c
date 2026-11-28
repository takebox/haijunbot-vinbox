/*
 * Positive example：nonelockprotected write operation
 * Expected：should detect data_race_suspect
 */
#include <pthread.h>
int shared_data = 0;
void *thread_func(void *arg) {
  shared_data = 100; // Real risk:nonelockwrite
  return NULL;
}
int main() {
  pthread_t t;
  pthread_create(&t, NULL, thread_func, NULL);
  pthread_join(t, NULL);
  return 0;
}
