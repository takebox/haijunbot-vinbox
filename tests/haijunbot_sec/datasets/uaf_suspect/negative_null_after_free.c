/*
 * false positive test：UAF - freeafterassignNULL
 * vulnerabilitytype：use_after_free_suspect
 * note：freeimmediately afterpointersetNULLissafedefensive programmingpattern，
 *       notshouldfalse reported asUAFsuspect
 * Expected：notshould detectuse_after_free_suspect
 */
#include <stdlib.h>

void foo() {
    char *p = (char*)malloc(100);
    free(p);
    p = NULL;  /* Safe:freepost-placeNULL，prevent danglingnull pointer */
}

void bar() {
    int *arr = (int*)malloc(50 * sizeof(int));
    free(arr);
    arr = NULL;  /* Safe:freepost-placeNULL */
}
