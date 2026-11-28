/*
 * Negative example：scanfhaswidth limit
 * Expected：notshould detect scanf_no_width
 */
#include <stdio.h>
void foo() {
  char buf[100];
  scanf("%99s", buf); // Safe:haswidth limit
}
