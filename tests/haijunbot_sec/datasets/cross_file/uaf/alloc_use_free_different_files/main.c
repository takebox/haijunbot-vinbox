int main() {
    void* ptr = allocate_memory();
    use_memory(ptr);
    free_memory(ptr);
    use_memory(ptr);  // UAF: freeafteruse
    return 0;
}
