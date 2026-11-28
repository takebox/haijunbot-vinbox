/*
 * Positive example：inet_atonuse
 * Expected：should detect inet_legacy
 */
#include <arpa/inet.h>
void foo() {
  struct in_addr addr;
  inet_aton("127.0.0.1", &addr); // Real risk:old versionAPI
}
