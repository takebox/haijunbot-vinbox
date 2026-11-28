/*
 * Positive example：path concatenationnotverify
 * Expected：should detect taint_path_traversal
 */
#include <stdio.h>
#include <string.h>
void open_user_file(char *filename) {
  char path[256] = "/home/user/data/";
  strcat(path, filename); // Dangerous:notverifyfilenamewhether contains../etcpath traversalchar
  FILE *fp = fopen(path, "r");
  // ...
}
