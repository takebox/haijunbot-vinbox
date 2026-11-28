/*
 * Expecteddetectresult: notshouldreportvulnerability
 * trap: looks likeSQL injection，butactualissafestatic query
 * safepractice: staticSQLstatementorparameterized query
 */
#include <stdio.h>
#include <string.h>

void safe_static_query() {
  char query[256];
  // safe: fully staticSQLstatement
  strcpy(query, "SELECT * FROM users WHERE status = 'active'");
}

void safe_parameterized_simulation(int user_id) {
  char query[256];
  // safe: useintegerparameter（notis stringconcatenate）
  snprintf(query, sizeof(query), "SELECT * FROM users WHERE id = %d", user_id);
}

void safe_table_whitelist(const char *table) {
  char query[256];
  // safe: whitelistchecktable name
  const char *allowed_tables[] = {"users", "logs", "config"};
  int valid = 0;
  for (int i = 0; i < 3; i++) {
    if (strcmp(table, allowed_tables[i]) == 0) {
      valid = 1;
      break;
    }
  }
  if (valid) {
    snprintf(query, sizeof(query), "SELECT * FROM %s", table);
  }
}
