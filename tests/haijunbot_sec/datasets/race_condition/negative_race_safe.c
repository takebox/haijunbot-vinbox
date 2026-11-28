/*
 * Expecteddetectresult: notshouldreportvulnerability
 * safepractice: useatomic operationsorfiledescriptionsymbol
 */
#include <fcntl.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>

void safe_file_access(char *filename) {
  // safe: useopenandfstat，avoidTOCTOU
  int fd = open(filename, O_RDONLY);
  if (fd == -1)
    return;

  struct stat st;
  if (fstat(fd, &st) == 0) {
    // usefiledescriptionsymbol，avoid race
    FILE *fp = fdopen(fd, "r");
    if (fp) {
      char buffer[100];
      fgets(buffer, sizeof(buffer), fp);
      fclose(fp);
      return;
    }
  }
  close(fd);
}
