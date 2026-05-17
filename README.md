📘 PyMemSandbox: High-Performance C-Level Memory Management & JIT Engine in Pure Python
PyMemSandbox is an advanced, cross-platform library that brings C-level memory manipulation, custom memory pooling, and Just-In-Time (JIT) machine code execution directly into Python. Built purely with Python's ctypes, it requires no C/C++ compilation and works seamlessly on Windows, Linux, and macOS (including Apple Silicon).
Whether you are building a secure AI code execution sandbox, optimizing high-frequency trading systems, or experimenting with low-level shellcode, PyMemSandbox provides the ultimate control over your system's memory.
✨ Key Features
🛡️ Secure Sandboxing: Isolate memory allocations within a controlled pool. Prevents memory leaks and limits resource usage.
⚡ High-Performance Memory Pool: Drastically reduces allocation overhead by batching memory requests (ideal for games and data processing).
🚀 JIT Code Execution: Dynamically write and execute raw machine code (bytes) at runtime.
🔧 Manual Memory Management: Full control with alloc, free, and realloc operations, bypassing Python's Garbage Collector (GC).
💥 Crash Protection: Intercepts low-level hardware exceptions (like Segmentation Faults) and converts them into manageable Python exceptions.
🌍 Cross-Platform: Automatically adapts to Windows (VirtualAlloc), Linux (mmap), and macOS (mmap + __clear_cache for ARM64).
📦 Installation
You can install the library directly by including the pymemsandbox.py file in your project, or via pip (if published):
bash

编辑



pip install pymemsandbox
🚀 Quick Start
1. Local Sandboxed Execution (JIT)
Execute raw machine code safely within an isolated memory pool.
python

编辑



from pymemsandbox import MemoryPoolSandbox, enable_crash_protection

# Enable protection against low-level crashes (SegFaults, etc.)
enable_crash_protection()

# x86_64 Machine Code: mov eax, 42; ret (Returns the integer 42)
# For Apple M1/M2/M3 (ARM64), use: b'\x2A\x00\x80\x52\xC0\x03\x5F\xD6'
machine_code = b'\xB8\x2A\x00\x00\x00\xC3'

try:
    # Create a 1MB isolated memory sandbox
    with MemoryPoolSandbox(pool_size_mb=1) as sandbox:
        # Inject and compile machine code
        my_func = sandbox.allocate_code(machine_code)
        
        # Execute the dynamically generated code
        result = my_func()
        print(f"JIT Execution Result: {result}")  # Output: 42

except Exception as e:
    print(f"Execution failed: {e}")
2. Global Memory Pool (High Performance)
Take over Python's memory allocation globally to boost performance and reduce GC overhead.
python

编辑



from pymemsandbox import enable_global_pool, disable_global_pool, global_pool

# Activate a 64MB global memory pool
enable_global_pool(pool_size_mb=64)

# Manually allocate memory from the global pool
ptr = global_pool.manual_alloc(10, dtype=ctypes.c_int)
ptr.assign(12345)
print(f"Value: {ptr.dereference()}")  # Output: 12345

# Deactivate and free all global memory
disable_global_pool()
🛠️ Detailed API Reference
🧩 MemoryPoolSandbox
A context manager that creates an isolated, executable memory pool. Memory is automatically freed when exiting the with block.
__init__(pool_size_mb=64)
pool_size_mb (int): The size of the sandbox memory pool in Megabytes.
allocate_code(machine_code: bytes)
Injects raw machine code into the pool, marks it as executable, and returns a callable Python function.
manual_alloc(size: int, dtype=ctypes.c_byte)
Manually allocates a block of memory within the sandbox. Returns a Pointer object.
manual_realloc(ptr: Pointer, new_size: int, dtype=ctypes.c_byte)
Resizes an existing memory block. Copies data to a new location if necessary.
manual_free(ptr: Pointer)
Logically frees the memory block (marks it for reuse within the pool).
🌍 Global Memory Pool
A singleton memory pool that persists across the application lifecycle.
enable_global_pool(pool_size_mb=64)
Activates the global memory接管 (takeover) mode with a specified pool size.
disable_global_pool()
Deactivates the global pool and releases all allocated memory back to the OS.
global_pool.manual_alloc(size, dtype)
Allocates memory from the active global pool.
global_pool.manual_realloc(ptr, new_size, dtype)
Resizes a memory block within the global pool.
global_pool.manual_free(ptr)
Frees memory in the global pool.
🧠 Pointer Object
Simulates C-style pointers for direct memory manipulation.
dereference(): Reads the value at the pointer's address.
assign(value): Writes a value to the pointer's address.
as_function(restype, argtypes): Casts the memory address to a callable C function (used internally by allocate_code).
Arithmetic: Supports addition/subtraction (e.g., ptr + 1 moves the pointer by sizeof(dtype)).
🛡️ Crash Protection
enable_crash_protection():
Enables faulthandler and registers signal handlers (for Unix/macOS) to catch SIGSEGV (Segmentation Fault) and SIGILL (Illegal Instruction). Converts these fatal errors into a Python DynamicCodeRuntimeError.
⚠️ Safety & Compatibility Notes
Architecture Specifics: When using allocate_code, ensure your machine_code bytes match the CPU architecture (x86_64 vs. ARM64).
Antivirus Software: Some antivirus software may flag dynamic code execution (JIT) as suspicious behavior. This is a false positive common to all JIT engines.
Windows Limitations: While faulthandler will print stack traces on crashes, converting Windows Structured Exceptions (SEH) into Python exceptions is limited compared to Unix signal handling.
📄 License
