/*
 * Expecteddetectresult: notshouldreportvulnerability
 * safepractice: usesafealternativefunction
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/random.h>
#include <time.h>

void safe_functions() {
  char buffer[100];

  // safe: usewithbounds checkofscanf
  scanf("%99s", buffer);

  // safe: usestrtok_rthreadsafeversion
  char str[] = "hello world";
  char *saveptr;
  char *token = strtok_r(str, " ", &saveptr);

  // safe: usegetrandomorarc4random
  unsigned int random;
  getrandom(&random, sizeof(random), 0);

  // safe: uselocaltime_rthreadsafeversion
  time_t t = time(NULL);
  struct tm tm_result;
  localtime_r(&t, &tm_result);

  // safe: copygetenvresult
  char *home = getenv("HOME");
  if (home) {
    char home_copy[256];
    strncpy(home_copy, home, sizeof(home_copy) - 1);
    home_copy[sizeof(home_copy) - 1] = '\0';
  }
}
