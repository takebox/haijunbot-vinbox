/*
 * cross_filepath traversal - inputgetmodule
 * user inputfrom nowfileget，cross_filepropagate tofileoperation
 */
#include <stdio.h>
#include <stdlib.h>

/* fromusergetfilename */
const char *get_filename(void) {
    static char buf[256];
    printf("Enter filename: ");
    fgets(buf, sizeof(buf), stdin);
    return buf;
}
