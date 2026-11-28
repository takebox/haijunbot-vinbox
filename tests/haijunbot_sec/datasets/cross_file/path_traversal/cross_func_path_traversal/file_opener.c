/*
 * cross_filepath traversal - fileoperationmodule
 * concatenateafterpathherefileused foropenfile
 */
#include <stdio.h>
#include <fcntl.h>

/* usefopenopenfile */
FILE *open_file_read(const char *path) {
    return fopen(path, "r");  /* openmaytraversedpath */
}

/* useopenopenfile */
int open_file_fd(const char *path) {
    return open(path, O_RDONLY);  /* openmaytraversedpath */
}
