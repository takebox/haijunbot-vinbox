/*
 * Negative example：constglobalvariable
 * Expected：notshould detect data_race_suspect
 */
#include <pthread.h>
const int shared_data = 0; // const，read-only
void *thread_func(void *arg) {
  int val = shared_data;
  return NULL;
}
int main() {
  pthread_t t;
  pthread_create(&t, NULL, thread_func, NULL);
  pthread_join(t, NULL);
  return 0;
}
