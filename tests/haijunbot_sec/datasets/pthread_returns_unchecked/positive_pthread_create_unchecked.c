/*
 * Positive example：pthread_createreturnvalueunchecked
 * Expected：should detect pthread_returns_unchecked
 */
#include <pthread.h>
void foo() {
  pthread_t t;
  pthread_create(&t, NULL, NULL, NULL); // Real risk:uncheckedreturnvalue
}
