/*
 * cross_fileSQL injection - main entry
 * vulnerabilitytype：sql_injection (cross_file)
 * missed detection reason：user inputcross_filepropagate toSQLexecute，
 *          c_checkerof_rule_sql_injectiononlydetection unitfilewithinsprintf/snprintfconcatenate
 * data flow：main.c -> input.c(get_user_input) -> query_builder.c(build_select_query) -> executor.c(execute_query)
 * Expected：should detectsql_injection，but current version due tocross_filemissed detection due to analysis limits
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern const char *get_user_input(void);
extern void build_select_query(char *sql, const char *username);
extern void execute_query(void *conn, const char *sql);

int main(void) {
    char sql[512];
    void *conn = NULL;  /* simplify，actualshouldinitializeMySQLconnect */

    /* cross_fileSQL injectiondata flow */
    const char *username = get_user_input();     /* input.c: getuser input */
    build_select_query(sql, username);           /* query_builder.c: concatenateSQL */
    execute_query(conn, sql);                    /* executor.c: executeSQL */

    return 0;
}
