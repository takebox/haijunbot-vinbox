/**
 * negative_cross_func.c
 * 
 * bypass strategy：passglobalvariable andcross-functionassign，makenull pointerpassglobalvariablepass。
 * detector _ast_null_deref_check forglobalvariabledirectskip（the5616line：if var_name in global_vars: continue），
 * notcheckglobalwhether variablemayforNULL。
 * 
 * vulnerabilityposition：main() in global_item->value = 42，among which global_item in init_global() set in NULL，
 * actualwill definitely crash at runtime。
 */

#include <stdio.h>
#include <stdlib.h>

typedef struct {
    int value;
} Item;

// globalvariable，ASTdetector regards as"safe"（notwill beNULL）
Item *global_item;

void init_global() {
    global_item = NULL;  // set global variable toNULL
}

int main(int argc, char **argv) {
    init_global();  // cross-function：set global variable in another function toNULL
    global_item->value = 42;  // dereferenceNULL，butglobal_varsdirectskip，no alert generated
    printf("value=%d\n", global_item->value);
    return 0;
}
