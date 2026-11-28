/*
 * Negative example：verifypathsafeproperty
 * Expected：notshould detect taint_path_traversal
 */
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
bool is_safe_filename(const char *filename) {
  // checkwhether containspath traversalchar
  return strstr(filename, "..") == NULL && strchr(filename, '/') == NULL;
}
void safe_open_file(const char *filename) {
  if (is_safe_filename(filename)) {
    char path[256] = "/home/user/data/";
    strcat(path, filename); // Safe:alreadyverifyfilenamenot containdangerouschar
    FILE *fp = fopen(path, "r");
  }
}
