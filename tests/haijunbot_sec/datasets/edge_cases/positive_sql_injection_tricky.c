/*
 * Expected detection result: should detectSQL injection
 * trap: looks likeusedoneparameterize，butactualstill isconcatenate
 * vulnerability type: hiddenofSQL injection
 */
#include <stdio.h>
#include <string.h>

void tricky_sql_injection(char *user_id) {
  char query[500];
  // trap: looks likeparameterized query，actualstill a stringconcatenate
  snprintf(query, sizeof(query), "SELECT * FROM users WHERE id = '%s'",
           user_id); // SQL injection!
}

void sql_via_concat(char *table, char *condition) {
  char query[1000];
  strcpy(query, "SELECT * FROM ");
  // trap: table nameconcatenate
  strcat(query, table); // SQL injection!
  strcat(query, " WHERE ");
  strcat(query, condition); // SQL injection!
}

void hidden_sql_injection(char *input) {
  char query[256];
  // trap: usesprintflooks like"safe"，but still isconcatenate
  sprintf(query, "DELETE FROM logs WHERE name='%s'", input); // SQL injection!
}
