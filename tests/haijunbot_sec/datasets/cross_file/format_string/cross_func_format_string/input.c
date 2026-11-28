/*
 * cross_fileformat string - inputgetmodule
 * user inputfrom nowfileget，cross_filepropagate to formattingoutput
 */
#include <stdio.h>
#include <stdlib.h>

/* fromuserget message format */
const char *get_message_format(void) {
    static char buf[256];
    printf("Enter log format: ");
    fgets(buf, sizeof(buf), stdin);
    return buf;
}

/* get from environment variable */
const char *get_env_format(const char *var) {
    return getenv(var);  /* environment variablemaycontrolled by attacker */
}
