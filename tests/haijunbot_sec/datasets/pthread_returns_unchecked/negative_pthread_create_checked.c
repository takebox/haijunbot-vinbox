/*
 * Negative example：pthread_createreturnvalue alreadycheck
 * Expected：notshould detect pthread_returns_unchecked
 */
#include <pthread.h>
void foo() {
  pthread_t t;
  if (pthread_create(&t, NULL, NULL, NULL) != 0) {
    return; // Safe:hascheck
  }
}
