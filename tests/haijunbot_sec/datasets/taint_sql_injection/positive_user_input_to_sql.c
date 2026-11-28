// SQL injectionPositive example:user input -> SQLstatementconcatenate
// should detect：user input directly concatenatedtoSQLstatement

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void vulnerable_query(const char *username) {
  char sql[256];

  // taint sink：user inputconcatenatetoSQLstatement
  // taint propagationpath：argv -> username -> sprintf -> sql
  sprintf(sql, "SELECT * FROM users WHERE name='%s'", username); // SQL injectionrisk

  printf("Executing: %s\n", sql);
}

int main(int argc, char *argv[]) {
  if (argc > 1) {
    // taint source：command lineparameter
    vulnerable_query(argv[1]);
  }
  return 0;
}
