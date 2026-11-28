/*
 * Positive example：functionreturnpointerunchecked
 * Expected：should detect function_return_ptr_no_check
 */
#include <stdlib.h>
char *get_buffer() { return malloc(100); }
void foo() {
  char *p = get_buffer();
  p[0] = 'x'; // Real risk:uncheckedreturnvalue
}
