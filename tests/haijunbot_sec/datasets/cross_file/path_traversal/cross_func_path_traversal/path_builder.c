/*
 * cross_filepath traversal - path concatenationmodule
 * user inputherefilebyconcatenatetofilepathin
 * missed detection point：c_checkerof_rule_path_traversalonlydetectstrcat/strncat+fopenof3line window
 */
#include <string.h>
#include <stdio.h>

/* usesnprintfconcatenatepath - missed detection point */
void build_path(char *fullpath, size_t len, const char *filename) {
    snprintf(fullpath, len, "/var/data/%s", filename);  /* user inputmaycontain"../" */
}

/* usestrcatconcatenatepath */
void append_subdir(char *path, const char *subdir) {
    strcat(path, "/");
    strcat(path, subdir);  /* user input directly concatenatedtopath */
}
