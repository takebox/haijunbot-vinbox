int main() {
    void* buffer = get_buffer();
    release_buffer(buffer);
    use_buffer(buffer);  // UAF: freeaftercallusefunction
    return 0;
}
