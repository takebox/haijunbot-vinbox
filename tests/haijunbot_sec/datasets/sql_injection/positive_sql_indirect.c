/*
 * Negative example (bypass)：mysql_query usemulti-levelpointerindirectreferenceuser input
 * Expected: detector should detect, but：
 * 1) K&R styleparameterdefinition makes taint analysis unable to recognizeuser input source
 * 2) *query indirectreference makes heuristic regex mysql_query\([^,]+,\s*(\w+) cannot match variable name
 * vulnerability：query isusercontrollableof SQL string，directexecutearbitrary SQL
 */

void vulnerable(conn, query)
void *conn;
char **query;
{
    mysql_query(conn, *query);  /* directexecuteusercontrollableSQL */
}
