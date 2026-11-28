/*
 * Positive example：openuse0777permissions
 * Expected：should detect open_permissive_perms
 */
#include <fcntl.h>
void foo() {
  int fd = open("test.txt", O_CREAT, 0777); // Real risk:permissionstoo loose
}
