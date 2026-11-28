/*
 * Negative example：nonelockprotected read operation
 * Expected：notshould detect data_race_suspect or very low confidence
 */
#include <pthread.h>
int shared_data = 0;
void *thread_func(void *arg) {
  int val = shared_data; // read operation，risklower
  return NULL;
}
int main() {
  pthread_t t;
  pthread_create(&t, NULL, thread_func, NULL);
  pthread_join(t, NULL);
  return 0;
}
