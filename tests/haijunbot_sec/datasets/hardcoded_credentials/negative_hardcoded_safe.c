/*
 * Expecteddetectresult: notshouldreportvulnerability
 * safepractice: from environment variable or configfilereadcredentials
 */
#include <stdlib.h>
#include <string.h>

const char *get_db_password() {
  // safe: from environment variableread
  return getenv("DB_PASSWORD");
}

const char *get_api_key() {
  // safe: from environment variableread
  return getenv("API_KEY");
}

void connect_database_safe() {
  const char *password = get_db_password();
  if (password == NULL) {
    return; // errorhandle
  }
  // useobtained from environment variablecredentials
}
