// path traversalPositive example:user input -> open taint propagation
// should detect：user inputdirectused forfilepath，openreturnvalueunchecked
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
  // taint source：command lineparameter
  char *filename = argv[1];

  // taint sink：openfile
  // taint propagationpath：argv -> filename -> open
  int fd = open(filename, O_RDONLY); // path traversalrisk
  char buffer[100];
  read(fd, buffer, sizeof(buffer));
  close(fd);
  return 0;
}
