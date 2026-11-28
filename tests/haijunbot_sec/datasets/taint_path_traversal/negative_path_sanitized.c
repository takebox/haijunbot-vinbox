// path traversalNegative example:user input -> open has sanitization
// should not detect：user inputthroughpathsanitized and used forfileoperation

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

// sanitizefunction：removepath traversalchar
void sanitize_path(char *path) {
  char *p = path;
  while (*p) {
    if (*p == '/' || *p == '\\' || *p == '..') {
      *p = '_'; // replace withsafechar
    }
    p++;
  }
}

int main(int argc, char *argv[]) {
  if (argc > 1) {
    // taint source：command lineparameter
    char filename[256];
    strncpy(filename, argv[1], sizeof(filename) - 1);
    filename[sizeof(filename) - 1] = '\0';

    // sanitize：removepath traversalchar
    sanitize_path(filename);

    // taint sink：openfile（sanitized）
    int fd = open(filename, O_RDONLY); // Safe:sanitized

    if (fd >= 0) {
      char buffer[100];
      read(fd, buffer, sizeof(buffer));
      close(fd);
    }
  }
  return 0;
}
