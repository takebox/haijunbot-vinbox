#include <stdlib.h>

// externalfunctiondeclare
extern void *allocate_memory();
extern void use_memory(void *ptr);
extern void free_memory(void *ptr);

// main function：democross_fileUAF
int main() {
  void *ptr = allocate_memory(); // alloc.c
  use_memory(ptr);               // use.c - first timeuse
  free_memory(ptr);              // free.c - free
  use_memory(ptr);               // use.c - UAF! use after free
  return 0;
}
