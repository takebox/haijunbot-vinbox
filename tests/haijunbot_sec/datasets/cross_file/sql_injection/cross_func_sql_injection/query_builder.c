/*
 * cross-file SQL injection - SQL concatenation module
 * user input in this file concatenated into SQL statement
 */
#include <string.h>
#include <stdio.h>

/* use strcat to concatenate SQL - missed detection: c_checker only detects sprintf/snprintf */
void build_select_query(char *sql, const char *username) {
    strcpy(sql, "SELECT * FROM users WHERE name='");
    strcat(sql, username);  /* user input directly concatenated */
    strcat(sql, "'");
}

/* use snprintf to concatenate SQL */
void build_delete_query(char *sql, size_t len, const char *record_id) {
    snprintf(sql, len, "DELETE FROM records WHERE id=%s", record_id);
}
