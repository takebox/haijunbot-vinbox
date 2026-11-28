#include <pthread.h>
#include <stdio.h>

pthread_mutex_t lockA = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t lockB = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t cond = PTHREAD_COND_INITIALIZER;

void *thread1_func(void *arg) {
  // thread1: holdlockA，waitcondition variable，also needlockB
  pthread_mutex_lock(&lockA);
  printf("Thread1: lockA acquired, waiting for condition\n");

  // while holdinglockAwait under conditioncondition variable
  // ifthread2needlockAcan send signal，will thendeadlock
  pthread_cond_wait(&cond, &lockA);

  pthread_mutex_lock(&lockB);
  printf("Thread1: lockB acquired\n");
  pthread_mutex_unlock(&lockB);
  pthread_mutex_unlock(&lockA);
  return NULL;
}

void *thread2_func(void *arg) {
  // thread2: needlockAandlockBcan send signal
  pthread_mutex_lock(&lockB);
  printf("Thread2: lockB acquired\n");

  pthread_mutex_lock(&lockA); // waitlockA，butthread1holdlockAand wait condition
  printf("Thread2: lockA acquired, signaling\n");

  pthread_cond_signal(&cond);
  pthread_mutex_unlock(&lockA);
  pthread_mutex_unlock(&lockB);
  return NULL;
}

int main() {
  pthread_t t1, t2;
  pthread_create(&t1, NULL, thread1_func, NULL);
  pthread_create(&t2, NULL, thread2_func, NULL);

  pthread_join(t1, NULL);
  pthread_join(t2, NULL);
  return 0;
}
