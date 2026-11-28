/*
 * cross_fileformat string - main entry
 * vulnerabilitytype：format_string (cross_file)
 * missed detection reason：user inputcross_filepropagate to formattingoutputfunction，
 *          c_checkerof_rule_format_stringnot coveredsyslog/erretcfunction
 * data flow：main.c -> input.c(get_message_format) -> logger.c(log_message)
 * Expected：should detectformat_string，but current version due tocross_fileanalysis limits andfunctionoverridenotcomplete but missed
 */
#include <stdio.h>
#include <stdlib.h>

extern const char *get_message_format(void);
extern void log_message(const char *fmt);
extern void print_formatted(const char *fmt, int value);

int main(void) {
    /* cross_fileformat stringdata flow */
    const char *fmt = get_message_format();  /* input.c: getuser input */
    log_message(fmt);                        /* logger.c: sysloguseuser inputasformat string */
    print_formatted(fmt, 42);                /* logger.c: printfuseuser inputasformat string */

    return 0;
}
