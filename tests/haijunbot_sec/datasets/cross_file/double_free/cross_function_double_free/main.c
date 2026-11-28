int main() {
    void* ptr = malloc(100);
    my_free(ptr);
    my_free(ptr);  // Double Free: repeatfree
    return 0;
}
