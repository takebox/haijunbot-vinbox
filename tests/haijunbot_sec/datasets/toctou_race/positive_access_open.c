/*
 * false positive test：TOCTOU - accessimmediately afteropen（3inline，shouldbydetect）
 * vulnerabilitytype：toctou_race
 * note：accessandopeninterval in5within line window，shouldbycorrectdetect
 * Expected：should detecttoctou_race（this is realTOCTOUvulnerability）
 */
#include <unistd.h>
#include <fcntl.h>

void check_and_open_immediate(const char *filename) {
    if (access(filename, R_OK) == 0) {
        int fd = open(filename, O_RDONLY);  /* closely followaccess，in5within line window */
        if (fd >= 0) close(fd);
    }
}
