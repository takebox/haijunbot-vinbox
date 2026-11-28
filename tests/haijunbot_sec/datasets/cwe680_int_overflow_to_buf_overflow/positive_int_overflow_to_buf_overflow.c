/*
 * Expected detection result: should detectinteger overflow leading to buffer overflow vulnerability
 * vulnerability type: CWE-680: Integer Overflow to Buffer Overflow
 * description: integer overflow causes insufficient buffer allocation, subsequent write causes overflow
 */
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

// Scenario1: multiplication overflow causes insufficient allocation
void multiply_overflow_alloc(size_t count, size_t elem_size) {
    // vulnerability: count * elem_size may overflow, causing too-small buffer allocation
    size_t total = count * elem_size;
    char *buffer = (char *)malloc(total);
    if (buffer) {
        // subsequent write assumes space for count elements, but actual may be very small after overflow
        for (size_t i = 0; i < count; i++) {
            buffer[i * elem_size] = 'x';  // may out of bounds write
        }
        free(buffer);
    }
}

// Scenario2: addition overflow causes insufficient allocation
void add_overflow_alloc(size_t base_size, size_t extra) {
    // vulnerability: base_size + extra may overflow
    size_t total = base_size + extra;
    char *buffer = (char *)malloc(total);
    if (buffer) {
        // write base_size bytes, but actual allocation may be very small
        memset(buffer, 'A', base_size);  // may out of bounds write
        free(buffer);
    }
}

// Scenario3: size_t wraparound causes 0-byte allocation
void wraparound_alloc(size_t user_size) {
    // vulnerability: user_size + 1 may wraparound to 0
    size_t alloc_size = user_size + 1;
    char *buffer = (char *)malloc(alloc_size);  // may allocate 0 bytes
    if (buffer) {
        // write user_size bytes, but buffer actually 0
        memset(buffer, 'B', user_size);  // definite out of bounds write
        free(buffer);
    }
}

// Scenario4: array index calculation overflow
void index_overflow_alloc(int index, int offset) {
    // vulnerability: index + offset may overflow
    int target = index + offset;
    char buffer[100];
    if (target >= 0 && target < 100) {
        buffer[target] = 'C';  // check may pass，but target may actually overflow
    }
}
