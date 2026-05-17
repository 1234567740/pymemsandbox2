Here is the updated, comprehensive PyMemSandbox Technical Manual.
I have revised the Architecture and Memory Management sections to explicitly emphasize the 64MB Default Memory Pool limit and added a dedicated Use Cases section to demonstrate practical applications.
📘 PyMemSandbox: Comprehensive Technical Manual
Version: 1.0.0
Language: Python (CPython Bindings)
Core Technology: Low-level Memory Mapping & JIT Compilation
1. Introduction
PyMemSandbox is a specialized library designed for high-performance computing tasks that require deterministic memory management and Just-In-Time (JIT) execution. Unlike standard Python, which relies on the Garbage Collector (GC) and dynamic object allocation, PyMemSandbox allocates a fixed, contiguous block of raw memory at initialization.
This approach eliminates GC pauses and object header overhead, making it ideal for:
High-frequency data processing.
Implementing custom data structures (e.g., B-Trees, Hash Maps).
Educational simulations of operating system memory management.
2. Architecture: The 64MB Sandbox
The defining feature of PyMemSandbox is its isolated memory environment.
⚙️ The 64MB Default Pool
Upon initialization, PyMemSandbox allocates a default contiguous memory pool of 64 Megabytes (64MB).
Why 64MB? This size is carefully chosen to be large enough for complex data structures and algorithms, yet small enough to prevent accidental system resource exhaustion during testing or recursive allocation errors.
How it works: The library uses memory mapping (mmap) or C-standard malloc to reserve this space. All subsequent memory operations (alloc, free) occur within this specific 64MB window.
Boundary Safety: The Memory Manager strictly enforces this limit. Attempting to allocate memory beyond the available 64MB capacity will raise a MemoryOverflowError rather than crashing the interpreter.
Note: This sandboxed approach ensures that memory leaks are contained within the pool and can be instantly reclaimed by destroying the pool object, rather than relying on Python's garbage collector.
3. Installation & Setup
To install the library from the source distribution:
bash

编辑



# Ensure you are in the project directory containing setup.py
python -m build
pip install dist/pymemsandbox-1.0.0-py3-none-any.whl
4. API Reference
4.1 MemoryPool Class
The MemoryPool class manages the 64MB space.
__init__(size_mb=64): Initializes the pool. The default size is 64MB.
alloc(size: int) -> int:
Allocates a block of raw memory of size bytes.
Returns: The relative memory address (pointer) as an integer.
Returns: 0 or raises an Exception if the 64MB limit is exceeded.
free(address: int): Releases the memory at the specific address back to the pool.
write(address: int, value: Any, dtype: str): Writes data to a specific address.
read(address: int, dtype: str) -> Any: Reads data from a specific address.
4.2 JITCompiler Class
compile(func): Compiles a Python function into native machine code within the sandbox.
execute(address): Executes the compiled code.
5. Practical Use Cases
Here are three distinct scenarios demonstrating how to utilize the 64MB pool effectively.
Case 1: High-Performance Integer Array
Standard Python lists are heavy because they store pointers to objects. Using PyMemSandbox, we can store raw integers contiguously, saving massive amounts of space and improving cache locality.
python

编辑



from pymemsandbox import MemoryPool

# 1. Initialize the 64MB Pool
pool = MemoryPool() 
print(f"Total Pool Size: {pool.total_size} bytes") # Output: 67108864 (64MB)

# 2. Allocate memory for 1,000,000 integers (4 bytes each)
# Total needed: 4,000,000 bytes (~3.8MB), well within the 64MB limit.
num_count = 1_000_000
buffer_size = num_count * 4 
start_addr = pool.alloc(buffer_size)

if start_addr:
    # 3. Write data directly to memory
    for i in range(num_count):
        # Writing integer 'i' at offset 'i * 4'
        pool.write(start_addr + (i * 4), i, dtype='int')

    # 4. Read data back
    val = pool.read(start_addr + 400, dtype='int') # Read the 100th integer
    print(f"Value at index 100: {val}") # Output: 100
    
    # 5. Cleanup
    pool.free(start_addr)
Case 2: Implementing a Custom Memory-Efficient Stack
You can use the sandbox to implement data structures that persist without Python's object overhead.
python

编辑



class RawMemoryStack:
    def __init__(self, pool, max_size):
        self.pool = pool
        # Allocate memory for the stack structure itself
        self.buffer = pool.alloc(max_size * 4) # Assuming 4-byte integers
        self.sp = 0 # Stack Pointer
        self.max_size = max_size

    def push(self, val):
        if self.sp >= self.max_size:
            raise OverflowError("Stack Full")
        # Write value at current stack pointer position
        self.pool.write(self.buffer + (self.sp * 4), val, 'int')
        self.sp += 1

    def pop(self):
        if self.sp == 0:
            raise IndexError("Stack Empty")
        self.sp -= 1
        return self.pool.read(self.buffer + (self.sp * 4), 'int')

# Usage
pool = MemoryPool() # 64MB Pool
stack = RawMemoryStack(pool, max_size=5000) # Uses ~19KB of the pool

stack.push(10)
stack.push(20)
print(stack.pop()) # Output: 20
Case 3: Handling Memory Exhaustion (The 64MB Limit)
This example demonstrates how the system behaves when you try to exceed the default 64MB limit.
python

编辑



from pymemsandbox import MemoryPool, MemoryOverflowError

pool = MemoryPool() # Default 64MB

# Attempt to allocate 70MB (exceeds default limit)
try:
    print("Attempting to allocate 70MB...")
    huge_block = pool.alloc(70 * 1024 * 1024)
except MemoryOverflowError as e:
    print(f"Allocation Failed: {e}")
    # Output: Allocation Failed: Cannot allocate 73400320 bytes. Pool limit (64MB) exceeded.
6. Troubleshooting
表格
Error	Cause	Solution
MemoryOverflowError	You attempted to allocate more memory than is available in the 64MB pool.	Check your allocation sizes. If necessary, re-initialize the pool with a larger size (if supported) or free unused memory blocks using free().
Segmentation Fault	You are reading/writing to an address that was not allocated (invalid pointer).	Ensure you are calculating offsets correctly (e.g., address + index * 4).
End of Manual

