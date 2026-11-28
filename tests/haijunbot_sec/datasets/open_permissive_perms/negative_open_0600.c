/*
 * Negative example：openuse0600permissions
 * Expected：notshould detect open_permissive_perms
 */
#include <fcntl.h>
void foo() {
  int fd = open("test.txt", O_CREAT, 0600); // Safe:permissionsreasonable
}
