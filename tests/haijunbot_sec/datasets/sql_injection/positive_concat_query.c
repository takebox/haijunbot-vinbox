/*
 * Positive example：SQLstringconcatenate
 * Expected：should detect sql_injection
 */
#include <stdio.h>
#include <string.h>
void execute_user_query(char *user_id) {
  char query[256];
  sprintf(query, "SELECT * FROM users WHERE id = %s", user_id);
  // Dangerous:directconcatenateuser inputtoSQLstatement
  printf("Executing: %s\n", query);
}
