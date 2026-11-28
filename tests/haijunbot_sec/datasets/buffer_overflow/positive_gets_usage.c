/*
 * Positive example：usegetsfunction
 * Expected：should detect buffer_overflow
 */
#include <stdio.h>
void vulnerable_input() {
  char buffer[100];
  gets(buffer); // Dangerous:getsdoes not check bounds，may cause buffer overflow
}
