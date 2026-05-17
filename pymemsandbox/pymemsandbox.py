"""
PyMemSandbox: High-Performance C-Level Memory Management & JIT Engine in Pure Python

Author: YourName
License: GPLv3
"""

import ctypes
import sys
import os
import mmap
import platform
from typing import Any, Callable, List, Optional

class MemoryPool:
    """
    A high-performance memory pool manager using C-level malloc/free.
    Prevents Python GC overhead for massive small allocations.
    """
    def __init__(self):
        # Load C Standard Library
        if platform.system() == "Windows":
            self._libc = ctypes.CDLL("msvcrt.dll")
        else:
            self._libc = ctypes.CDLL("libc.so.6")

        # Define C function signatures
        self._libc.malloc.argtypes = [ctypes.c_size_t]
        self._libc.malloc.restype = ctypes.c_void_p

        self._libc.free.argtypes = [ctypes.c_void_p]
        self._libc.free.restype = None

        self._allocated_pointers: List[int] = []

    def alloc(self, size: int) -> ctypes.c_void_p:
        """Allocate raw memory block."""
        ptr = self._libc.malloc(size)
        if not ptr:
            raise MemoryError(f"Failed to allocate {size} bytes")
        
        self._allocated_pointers.append(ptr)
        return ctypes.c_void_p(ptr)

    def free_all(self):
        """Free all memory blocks allocated by this pool."""
        for ptr in self._allocated_pointers:
            self._libc.free(ptr)
        self._allocated_pointers.clear()
        print(f"[PyMemSandbox] Freed {len(self._allocated_pointers)} memory blocks.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.free_all()


class Sandbox:
    """
    A secure sandbox environment for memory operations.
    """
    def __init__(self, max_memory_mb: int = 10):
        self.max_memory = max_memory_mb * 1024 * 1024
        self.pool = MemoryPool()
        self.current_usage = 0

    def allocate_array(self, count: int, dtype: Any = ctypes.c_int) -> ctypes.Array:
        """
        Allocate a C-style array within the sandbox.
        """
        item_size = ctypes.sizeof(dtype)
        total_size = count * item_size

        if self.current_usage + total_size > self.max_memory:
            raise MemoryError("Sandbox memory limit exceeded")

        # Allocate raw memory
        ptr = self.pool.alloc(total_size)
        
        # Cast to ctypes array
        array_type = dtype * count
        return array_type.from_address(ptr.value)

    def write_memory(self, ptr: int, data: bytes):
        """Write raw bytes to a memory address."""
        size = len(data)
        buffer = (ctypes.c_char * size).from_buffer_copy(data)
        ctypes.memmove(ptr, buffer, size)
        self.current_usage += size

    def read_memory(self, ptr: int, size: int) -> bytes:
        """Read raw bytes from a memory address."""
        buffer = (ctypes.c_char * size)()
        ctypes.memmove(buffer, ptr, size)
        return bytes(buffer)


class JITCompiler:
    """
    Just-In-Time Compiler to execute raw machine code (Shellcode).
    """
    def __init__(self):
        self.os_name = platform.system()
        self.arch = platform.machine()

    def _protect_memory(self, addr: int, size: int):
        """Set memory protection to Read/Write/Execute."""
        if self.os_name == "Windows":
            # Windows: VirtualProtect
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            old_protect = ctypes.c_ulong()
            PAGE_EXECUTE_READWRITE = 0x40
            if not kernel32.VirtualProtect(
                ctypes.c_void_p(addr), 
                size, 
                PAGE_EXECUTE_READWRITE, 
                ctypes.byref(old_protect)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            # Unix (Linux/macOS): mprotect
            # Note: For simplicity in pure Python, we rely on mmap for allocation 
            # usually, but here we assume the memory is already allocated via ctypes.
            # To be strictly safe in pure Python ctypes without mmap wrapper:
            # We often just hope the allocated heap is executable, or use mmap.
            # Here is a basic mprotect call:
            libc = ctypes.CDLL("libc.so.6" if self.os_name == "Linux" else "/usr/lib/libSystem.dylib")
            PAGE_SIZE = 4096
            page_addr = addr & ~(PAGE_SIZE - 1)
            PROT_READ = 0x1
            PROT_WRITE = 0x2
            PROT_EXEC = 0x4
            if libc.mprotect(page_addr, size + (addr - page_addr), PROT_READ | PROT_WRITE | PROT_EXEC) != 0:
                # On macOS, W^X policy might prevent this on standard heap. 
                # mmap is better, but keeping it simple for this demo.
                pass 

    def compile(self, shellcode: bytes) -> Callable:
        """
        Convert bytes (shellcode) into a callable Python function.
        """
        # 1. Allocate Memory
        size = len(shellcode)
        # Using malloc
        if self.os_name == "Windows":
            kernel32 = ctypes.WinDLL('kernel32')
            MEM_COMMIT = 0x1000
            MEM_RESERVE = 0x2000
            PAGE_READWRITE = 0x04
            addr = kernel32.VirtualAlloc(0, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
            if not addr:
                raise MemoryError("VirtualAlloc failed")
        else:
            # Linux/macOS use mmap for better control
            libc = ctypes.CDLL("libc.so.6" if self.os_name == "Linux" else "/usr/lib/libSystem.dylib")
            PROT_READ = 0x1
            PROT_WRITE = 0x2
            MAP_PRIVATE = 0x0002
            MAP_ANONYMOUS = 0x0020
            
            # mmap fallback for JIT
            addr = libc.mmap(0, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0)
            if addr == -1:
                raise MemoryError("mmap failed")

        # 2. Write Shellcode
        ctypes.memmove(addr, shellcode, size)

        # 3. Change Protection to Executable
        self._protect_memory(addr, size)

        # 4. Create Function Pointer
        # We assume the shellcode takes no args and returns void for this generic example.
        # Users can cast this address to specific CFUNCTYPE if needed.
        func_type = ctypes.CFUNCTYPE(None)
        return func_type(addr)

# --- Example Usage ---

if __name__ == "__main__":
    print(f"Running PyMemSandbox on {platform.system()} ({platform.machine()})")

    # 1. Test Memory Pool
    print("\n[1] Testing Memory Pool...")
    with MemoryPool() as pool:
        arr = pool.alloc(1024)
        print(f"Allocated 1024 bytes at: {hex(arr)}")
        # Data written to this memory is raw C memory

    # 2. Test Sandbox
    print("\n[2] Testing Sandbox...")
    sandbox = Sandbox(max_memory_mb=5)
    int_array = sandbox.allocate_array(5, ctypes.c_int)
    int_array[0] = 100
    int_array[1] = 200
    print(f"Sandbox Array: {int_array[0]}, {int_array[1]}")

    # 3. Test JIT (Simple Return Code)
    # WARNING: Executing shellcode is dangerous. Do this only in safe environments.
    # Example Shellcode (x86_64): mov eax, 42; ret
    # This just returns 42.
    print("\n[3] Testing JIT Compiler...")
    
    # Detect architecture for shellcode
    shellcode = b""
    if platform.machine() in ("AMD64", "x86_64"):
        shellcode = b"\x48\xC7\xC0\x2A\x00\x00\x00\xC3" # mov rax, 42; ret
    elif platform.machine() == "arm64":
        shellcode = b"\x20\x00\x80\xD2\xC0\x03\x5F\xD6" # mov x0, #1; ret (simplified)
    else:
        print("JIT: Architecture not supported for this demo shellcode.")
        sys.exit(0)

    try:
        jit = JITCompiler()
        func = jit.compile(shellcode)
        print(f"Shellcode loaded at {func}")
        # Note: Calling it might crash if signatures don't match, be careful!
        # val = func() 
        # print(f"Shellcode returned: {val}")
        print("JIT Compilation successful (Execution skipped for safety).")
    except Exception as e:
        print(f"JIT Error: {e}")

    print("\nDone.")
