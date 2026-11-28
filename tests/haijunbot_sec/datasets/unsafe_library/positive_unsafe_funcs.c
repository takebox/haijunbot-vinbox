/*
 * Expected detection result: should detectnotsafelibfunctionuse
 * vulnerability type: usedeprecated ornotsafeoffunction
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void unsafe_functions() {
  char buffer[100];

  // notsafe: scanfnonebounds check
  scanf("%s", buffer);

  // notsafe: strtoknonthreadsafe
  char str[] = "hello world";
  char *token = strtok(str, " ");

  // notsafe: randnotusable forsafepurpose
  int random = rand();

  // notsafe: localtimenonthreadsafe
  time_t t = time(NULL);
  struct tm *tm = localtime(&t);

  // notsafe: getenvreturnstaticbuffer
  char *home = getenv("HOME");
}
