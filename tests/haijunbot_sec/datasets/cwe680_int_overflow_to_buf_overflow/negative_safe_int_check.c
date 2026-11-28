/*
 * Expecteddetectresult: notshouldreportvulnerability
 * safepractice: usesafeofintegeroperationcheck，preventoverflow
 * note: current detectormayfalse positive on this case，this exposes room for detector improvement
 */
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>

// safeversion1: multiplication overflowcheck
void safe_multiply_alloc(size_t count, size_t elem_size) {
    // safe: checkmultiplicationwhether willoverflow
    if (count > 0 && elem_size > 0 && count <= SIZE_MAX / elem_size) {
        size_t total = count * elem_size;
        char *buffer = (char *)malloc(total);
        if (buffer) {
            for (size_t i = 0; i < count; i++) {
                buffer[i * elem_size] = 'x';
            }
            free(buffer);
        }
    }
}

// safeversion2: additionoverflowcheck
void safe_add_alloc(size_t base_size, size_t extra) {
    // safe: checkadditionwhether willoverflow
    if (base_size <= SIZE_MAX - extra) {
        size_t total = base_size + extra;
        char *buffer = (char *)malloc(total);
        if (buffer) {
            memset(buffer, 'A', base_size);
            free(buffer);
        }
    }
}

// safeversion3: usecallocavoidoverflow
void safe_calloc_alloc(size_t count, size_t elem_size) {
    // safe: callocinternally willcheckoverflow
    char *buffer = (char *)calloc(count, elem_size);
    if (buffer) {
        for (size_t i = 0; i < count; i++) {
            buffer[i * elem_size] = 'x';
        }
        free(buffer);
    }
}

// safeversion4: usesafeofAPI（likereallocarray）
void safe_reallocarray_alloc(size_t count, size_t elem_size) {
    // safe: reallocarraywillcheckmultiplication overflow
    char *buffer = NULL;
    // simulatereallocarrayofsafecheck
    if (count > 0 && elem_size > 0 && count <= SIZE_MAX / elem_size) {
        buffer = (char *)malloc(count * elem_size);
        if (buffer) {
            memset(buffer, 0, count * elem_size);
            free(buffer);
        }
    }
}
