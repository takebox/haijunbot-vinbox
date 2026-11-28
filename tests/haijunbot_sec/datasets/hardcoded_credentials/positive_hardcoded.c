/*
 * Expected detection result: should detecthardcoded credentials
 * vulnerability type: sensitive info hardencode
 */
#include <string.h>

// hardcoded password - saferisk
const char *DB_PASSWORD = "admin123";
const char *API_KEY = "sk-1234567890abcdef";
#define SECRET_KEY "my_secret_key_123"

void connect_database() {
  char password[] = "root_password"; // hardencode
  char *key = "AWS_SECRET_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE";

  // usehardcoded credentials
  if (strcmp(password, DB_PASSWORD) == 0) {
    // connect database
  }
}
