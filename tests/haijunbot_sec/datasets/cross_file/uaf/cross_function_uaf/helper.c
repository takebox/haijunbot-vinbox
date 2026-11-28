#include <stdlib.h>

void* get_buffer() {
    return malloc(100);
}

void use_buffer(void* buf) {
    // usememory
}

void release_buffer(void* buf) {
    free(buf);
}
