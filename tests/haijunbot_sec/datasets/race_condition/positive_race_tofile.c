/*
 * Expected detection result: should detectTOCTOUrace condition
 * vulnerability type: Time-of-check to time-of-use
 */
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>

void race_condition_vuln(char *filename) {
  // TOCTOU: checkanduserace window exists between
  if (access(filename, R_OK) == 0) {
    // race window: attackermayreplacefile
    FILE *fp = fopen(filename, "r"); // mayopendifferentfile
    if (fp) {
      char buffer[100];
      fgets(buffer, sizeof(buffer), fp);
      fclose(fp);
    }
  }
}

void race_symlink_vuln(char *path) {
  // race condition: lstatafteruse
  struct stat st;
  if (lstat(path, &st) == 0) {
    // race window
    FILE *fp = fopen(path, "w"); // possible symlink attack
    if (fp)
      fclose(fp);
  }
}
