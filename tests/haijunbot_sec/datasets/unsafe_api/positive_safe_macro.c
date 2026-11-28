/*
 * Negative example (bypass)：actualnotsafeof strcpy wrapped in named SAFE_COPY in macro
 * Expected：detectorshould detect strcpy，but DataCollector only record SAFE_COPY call（notbelong to UNSAFE_APIS）
 * vulnerability：src forusercontrollablememory，strcpy nonebounds check，cancausesbuffer overflow
 */
#include <string.h>

#define SAFE_COPY(dst, src) strcpy((dst), (src))

void test(char *dst, const char *user_input) {
    if (dst == NULL) return;
    SAFE_COPY(dst, user_input);  /* after macro expansion strcpy(dst, user_input) */
}
