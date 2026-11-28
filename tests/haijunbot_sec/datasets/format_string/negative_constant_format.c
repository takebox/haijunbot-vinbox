/*
 * Negative example：constantformat string
 * Expected：notshould detect format_string
 */
#include <stdio.h>
void foo(int x) {
  printf("%d\n", x); // Safe:constant format
}
