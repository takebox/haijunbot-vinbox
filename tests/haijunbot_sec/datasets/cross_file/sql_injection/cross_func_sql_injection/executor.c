/*
 * cross_fileSQL injection - SQLexecutemodule
 * concatenateafterSQLherefilebyexecute
 */
#include <mysql/mysql.h>

/* executeSQLquery */
void execute_query(MYSQL *conn, const char *sql) {
    mysql_query(conn, sql);  /* executemaybyinjectionofSQL */
}

/* executeSQLitequery - missed detection point：c_checkernot coveredsqlite3_exec */
void execute_sqlite(void *db, const char *sql) {
    sqlite3_exec((sqlite3*)db, sql, NULL, NULL, NULL);
}
