// Bypass 1: format_string - pass the format string indirectly through a pointer
// Expectation: should NOT report format_string (the format string comes from a const char*)
void format_bypass_1(void) {
    const char *fmt = "hello %s\n";
    const char **pfmt = &fmt;
    printf(*pfmt, "world");  // The format string is *pfmt -> "hello %s\n", actually safe
}

// Bypass 2: store the format string via a struct member
struct log_config {
    const char *format;
};

void format_bypass_2(struct log_config *cfg) {
    printf(cfg->format, 42);  // cfg->format should be set to a literal during initialization
}
