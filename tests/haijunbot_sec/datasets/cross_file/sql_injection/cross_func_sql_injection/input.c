/*
 * cross_fileSQL injection - inputgetmodule
 * user inputfrom nowfileget，cross_filepropagate toSQLexecute
 */
#include <stdio.h>
#include <stdlib.h>

/* fromusergetinput */
const char *get_user_input(void) {
    static char buf[256];
    printf("Enter username: ");
    fgets(buf, sizeof(buf), stdin);
    return buf;
}
