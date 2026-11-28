// SQL injectionNegative example:useparameterized query
// should not detect：useparameterized querypreventSQL injection

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void safe_query(const char *username) {
  // useparameterized query（simulate）
  const char *sql = "SELECT * FROM users WHERE name=?";

  printf("Executing: %s (parameter: %s)\n", sql, username); // Safe:parameterized query
}

int main(int argc, char *argv[]) {
  if (argc > 1) {
    // taint source：command lineparameter
    safe_query(argv[1]);
  }
  return 0;
}
