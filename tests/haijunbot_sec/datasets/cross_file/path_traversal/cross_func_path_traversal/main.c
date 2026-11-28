/*
 * cross_filepath traversal - main entry
 * vulnerabilitytype：path_traversal (cross_file)
 * missed detection reason：user inputcross_filepropagate tofileoperation，
 *          c_checkerof_rule_path_traversalonlydetection unitfileinstrcat+fopenof3line window
 * data flow：main.c -> input.c(get_filename) -> path_builder.c(build_path) -> file_opener.c(open_file_read)
 * Expected：should detectpath_traversal，but current version due tocross_filemissed detection due to analysis limits
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern const char *get_filename(void);
extern void build_path(char *fullpath, size_t len, const char *filename);
extern FILE *open_file_read(const char *path);

int main(void) {
    char path[512];

    /* cross_filepath traversaldata flow */
    const char *filename = get_filename();    /* input.c: getuser input */
    build_path(path, sizeof(path), filename); /* path_builder.c: concatenatepath */
    FILE *fp = open_file_read(path);          /* file_opener.c: openfile */

    if (fp) {
        char buf[128];
        fgets(buf, sizeof(buf), fp);
        fclose(fp);
    }

    return 0;
}
