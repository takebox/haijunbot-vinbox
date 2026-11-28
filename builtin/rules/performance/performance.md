---
name: performance
description: Triggered when code performance optimization or performance analysis is needed. Triggered whenever the user mentions "performance optimization", "performance analysis", "code tuning", "performance bottleneck", "optimize code", "improve performance", "performance testing". Not triggered: writing feature code without performance concerns; only reading code without modifications; discussing performance concepts without specific optimization actions.
---

---

## Rust Specialization: Rust Code Performance

## Basic Principles

- **Zero-cost abstractions**: Use Rust's zero-cost abstraction features without introducing runtime overhead
- **Ownership and borrowing**: Make good use of the ownership system to avoid unnecessary clones
- **Static dispatch**: Prefer generic static dispatch over trait object dynamic dispatch
- **Memory layout**: Optimize the memory layout of data structures to reduce cache misses

## Performance Analysis Tools

- **perf**: Linux performance analysis tool for analyzing CPU hotspots
- **flamegraph**: Generates flame graphs to visualize performance bottlenecks
- **cargo bench**: Benchmarking to measure code execution time
- **valgrind**: Memory analysis to detect memory leaks

## Common Optimization Strategies

### Ownership and Borrowing

```rust
// Inefficient: frequent cloning
fn process(data: Vec<u8>) {
    let cloned = data.clone(); // Unnecessary clone
    // ...
}

// Efficient: use a reference
fn process(data: &[u8]) {
    // Use the reference directly
}
```

### Memory Allocation

- Preallocate capacity: use `with_capacity` to preallocate Vec, String, etc.
- Reuse memory: reuse already allocated buffers
- Avoid small object allocation: use arrays or fixed-size structs

### Concurrency Optimization

- Use `Rayon` for data-parallel processing
- Use `crossbeam` for lock-free programming
- Use `tokio` for asynchronous I/O

### Compiler Optimization

- Enable LTO (Link Time Optimization)
- Use the `#[inline]` attribute to inline critical functions
- Use `target-cpu=native` to optimize for the local CPU

## Performance Checklist

- [ ] Used a Profiler to analyze performance bottlenecks
- [ ] Reduced unnecessary clones
- [ ] Preallocated collection capacity
- [ ] Used appropriate data structures
- [ ] Enabled compiler optimizations
- [ ] Run benchmark tests to verify
