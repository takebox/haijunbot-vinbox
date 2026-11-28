/*
 * false positive test：mallocuncheckedNULL - useassertcheck
 * vulnerabilitytype：alloc_no_null_check
 * note：useassert(ptr != NULL)is legitimateNULLcheckway，
 *       notshouldfalse reported as"uncheckedNULL"
 * Expected：notshould detectalloc_no_null_check
 */
#include <stdlib.h>
#include <assert.h>

void foo() {
    char *p = (char*)malloc(100);
    assert(p != NULL);  /* legitimateNULLcheckway */
    p[0] = 'x';
}

void bar() {
    int *arr = (int*)malloc(50 * sizeof(int));
    assert(arr);  /* assert(ptr)also legitimateNULLcheck */
    arr[0] = 42;
}
