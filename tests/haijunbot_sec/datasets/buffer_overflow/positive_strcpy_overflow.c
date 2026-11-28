/*
 * Positive example：strcpynonebounds check
 * Expected：should detect buffer_overflow
 */
#include <string.h>
void copy_user_input(char *user_input) {
  char buffer[100];
  strcpy(buffer, user_input); // Dangerous:if user_input exceeds 100 bytes will overflow
}
