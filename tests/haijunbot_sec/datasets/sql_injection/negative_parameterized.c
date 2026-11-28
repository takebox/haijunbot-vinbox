/*
 * Negative example：useparameterized query（simulate）
 * Expected：notshould detect sql_injection
 */
#include <stdio.h>
void safe_query(const char *user_id) {
  // Safe:useparameterized query（comment simulates here）
  // PREPARE stmt FROM 'SELECT * FROM users WHERE id = ?';
  // EXECUTE stmt USING user_id;
  printf("Using parameterized query for id: %s\n", user_id);
}
