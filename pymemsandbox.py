import ctypes
import sys
import os
import threading
import random
import warnings
from typing import Optional, Union, Tuple, Any, Dict, List

# ================= 跨平台常量与 C/C++ 底层内存映射 =================
OS_NAME = sys.platform
IS_WINDOWS = OS_NAME.startswith('win')
IS_LINUX = OS_NAME.startswith('linux')
DEFAULT_BLOCK_SIZE = 1024 * 1024  # 内存池单次向系统申请 1MB 的大块

# 映射 C 标准库的 malloc, free, memset
if IS_WINDOWS:
    msvcrt = ctypes.cdll.msvcrt
    c_malloc = msvcrt.malloc
    c_free = msvcrt.free
    c_memset = msvcrt.memset
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    # 预留 Windows API 接口以便扩展
    kernel32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    kernel32.VirtualAlloc.restype = ctypes.c_void_p
else:
    try:
        libc = ctypes.CDLL("libc.so.6")
    except OSError:
        libc = ctypes.CDLL("libc.dylib")
    c_malloc = libc.malloc
    c_free = libc.free
    c_memset = libc.memset

# GIL 优化：映射 Python C API 的线程状态保存与恢复函数
_py_eval_save = ctypes.pythonapi.PyEval_SaveThread
_py_eval_restore = ctypes.pythonapi.PyEval_RestoreThread
_py_eval_save.restype = ctypes.c_void_p
_py_eval_restore.argtypes = [ctypes.c_void_p]


# ================= 异常与指针类 =================
class WildPointerError(Exception):
    """精准野指针检测异常"""
    def __init__(self, message: str, frame_info: Optional[Tuple[str, int, str]] = None):
        super().__init__(message)
        self.frame_info = frame_info
        if frame_info:
            file, line, func = frame_info
            self.add_note(f"WildPointer detected at {file}:{line} in {func}()")


class Pointer:
    """C/C++ 风格的底层指针（支持 GIL 优化与边界检查）"""
    __slots__ = ('manager', 'address', 'offset')

    def __init__(self, manager, address: int, offset: int = 0):
        self.manager = manager
        self.address = address
        self.offset = offset

    def shift(self, offset: int) -> 'Pointer':
        """指针偏移"""
        return Pointer(self.manager, self.address, self.offset + offset)

    def _check_bounds(self, length: int, limit_addr: int, limit_size: int) -> None:
        """边界安全检查"""
        target_addr = self.address + self.offset
        if target_addr + length > limit_addr + limit_size or self.offset < 0:
            raise WildPointerProintError(f"Out of bounds access at {hex(target_addr)}")

    def read_int(self, limit_addr=0, limit_size=0) -> int:
        """读取 4 字节整数"""
        self._check_bounds(4, limit_addr, limit_size)
        state = _py_eval_save()
        try:
            int_ptr = ctypes.cast(self.address + self.offset, ctypes.POINTER(ctypes.c_int))
            return int_ptr.contents.value
        finally:
            _py_eval_restore(state)

    def write_int(self, value: int, limit_addr=0, limit_size=0) -> None:
        """写入 4 字节整数"""
        self._check_bounds(4, limit_addr, limit_size)
        state = _py_eval_save()
        try:
            int_ptr = ctypes.cast(self.address + self.offset, ctypes.POINTER(ctypes.c_int))
            int_ptr.contents.value = value
        finally:
            _py_eval_restore(state)

    def read_bytes(self, length: int, limit_addr=0, limit_size=0) -> bytes:
        """读取指定长度的字节"""
        self._check_bounds(length, limit_addr, limit_size)
        state = _py_eval_save()
        try:
            return ctypes.string_at(self.address + self.offset, length)
        finally:
            _py_eval_restore(state)

    def write_bytes(self, data: bytes, limit_addr=0, limit_size=0) -> None:
        """写入字节数据"""
        length = len(data)
        self._check_bounds(length, limit_addr, limit_size)
        state = _py_eval_save()
        try:
            ctypes.memmove(self.address + self.offset, data, length)
        finally:
            _py_eval_restore(state)


# ================= 核心：带有反作弊对抗机制的内存池 =================
class AntiCheatMemoryPool:
    """带有反作弊对抗机制的底层内存分配模型（中央仓库）"""
    
    def __init__(self, block_size: int = DEFAULT_BLOCK_SIZE):
        self.block_size = block_size
        self.free_list = None  # 空闲大块链表头
        self.allocated_blocks = []  # 记录所有向系统申请过的大块地址
        self.vital_data_map: Dict[int, int] = {}  # 核心数据地址映射 {addr: size}
        self._lock = threading.Lock()

    class MemoryBlock:
        __slots__ = ('address', 'size', 'offset', 'next_free')

        def __init__(self, address: int, size: int):
            self.address = address
            self.size = size
            self.offset = 0
            self.next_free = None

    def alloc(self, size: int, align: int = 8, camouflage: bool = True) -> int:
        """
        从中央池分配内存。
        注意：此方法会被 ThreadLocalCache 调用，内部已包含锁机制。
        """
        aligned_size = (size + align - 1) & ~(align - 1)
        
        if camouflage:
            # 内存伪装：额外分配前后各一段随机大小的伪装区
            aligned_size += random.randint(64, 256) * 2

        with self._lock:
            current = self.free_list
            prev = None
            
            # 寻找合适的空闲块
            while current:
                if current.size - current.offset >= aligned_size:
                    ptr = current.address + current.offset
                    current.offset += aligned_size
                    
                    # 如果开启了伪装，返回中间的真实区域地址
                    if camouflage:
                        ptr += random.randint(64, 128)
                    return ptr
                prev = current
                current = current.next_free

            # 向系统申请新的大块内存
            new_block_addr = c_malloc(self.block_size)
            if not new_block_addr:
                raise MemoryError("System malloc failed")
            
            self.allocated_blocks.append(new_block_addr)
            new_block = self.MemoryBlock(new_block_addr, self.block_size)
            
            if prev:
                prev.next_free = new_block
            else:
                self.free_list = new_block

        # 递归调用以在新块中分配 (释放锁后重试)
        return self.alloc(size, align, camouflage)

    def register_vital_data(self, addr: int, size: int):
        """注册需要动态漂移保护的核心数据"""
        with self._lock:
            self.vital_data_map[addr] = size

    def memory_drift(self):
        """内存动态漂移：迁移核心数据并注入花指令"""
        print("[Anti-Cheat] 正在执行内存动态漂移与花指令注入...")
        with self._lock:
            for old_addr, size in list(self.vital_data_map.items()):
                # 1. 读取旧数据
                old_data = ctypes.string_at(old_addr, size)
                # 2. 重新分配新地址 (关闭伪装防止无限叠加)
                new_addr = self.alloc(size, camouflage=False)
                # 3. 迁移数据
                ctypes.memmove(new_addr, old_data, size)
                # 4. 更新映射
                self.vital_data_map[new_addr] = size
                del self.vital_data_map[old_addr]
                # 5. 花指令注入：用随机数据覆盖旧地址
                random_junk = bytes([random.randint(0, 255) for _ in range(size)])
                ctypes.memmove(old_addr, random_junk, size)
        print("[Anti-Cheat] 内存漂移完成，旧特征码已失效！")

    def reset(self):
        """极速重置内存池（瞬态执行后抹除痕迹）"""
        with self._lock:
            current = self.free_list
            while current:
                current.offset = 0
                current = current.next_free
            self.vital_data_map.clear()

    def free_all(self):
        """彻底销毁内存池"""
        with self._lock:
            for addr in self.allocated_blocks:
                c_free(addr)
            self.allocated_blocks.clear()
            self.free_list = None


# ================= 新增：线程本地缓存 (TLS) =================
class ThreadLocalCache:
    """
    线程本地缓存（Thread Cache）。
    每个线程私有的“小仓库”，无锁分配与释放。
    """
    __slots__ = ('free_list', 'max_size', 'central_pool')

    def __init__(self, central_pool: AntiCheatMemoryPool, max_size: int = 50):
        self.central_pool = central_pool
        self.max_size = max_size
        self.free_list: List[int] = []

    def get(self, size: int, align: int = 8, camouflage: bool = True) -> int:
        """无锁获取内存"""
        if self.free_list:
            return self.free_list.pop()
        # 本地缓存空了，去中央池“批发” (此时加锁)
        return self.central_pool.alloc(size, align, camouflage)

    def put(self, ptr: int) -> None:
        """无锁归还内存"""
        if len(self.free_list) < self.max_size:
            self.free_list.append(ptr)
        else:
            # 本地满了，丢弃（由中央池管理生命周期，或在此处实现退回逻辑）
            pass


# ================= 全局内存控制器 (集成 TLS) =================
class GlobalMemoryController:
    """全局内存控制器：融合底层语法、反作弊对抗与线程本地存储(TLS)"""
    
    def __init__(self):
        self.pool = AntiCheatMemoryPool()
        self._tls = threading.local() # 线程本地存储对象

    def _get_cache(self) -> ThreadLocalCache:
        """获取当前线程的本地缓存"""
        if not hasattr(self._tls, 'cache'):
            self._tls.cache = ThreadLocalCache(self.pool)
        return self._tls.cache

    def alloc(self, size: int, camouflage: bool = True) -> int:
        """高级分配：优先从 TLS 获取，无锁"""
        return self._get_cache().get(size, camouflage=camouflage)

    def free(self, addr: int):
        """释放：优先放入 TLS 缓存，无锁"""
        if addr != 0:
            self._get_cache().put(addr)

    def malloc(self, size: int) -> int:
        """C 原生语法：直接向系统申请"""
        addr = c_malloc(size)
        if addr == 0:
            raise MemoryError("malloc failed")
        return addr

    def zero(self, addr: int, size: int):
        """C 语法：内存清零抹除"""
        if addr != 0:
            c_memset(addr, 0, size)

    def register_vital(self, addr: int, size: int):
        self.pool.register_vital_data(addr, size)

    def drift(self):
        self.pool.memory_drift()

    def reset_pool(self):
        self.pool.reset()

    def destroy(self):
        self.pool.free_all()


# ================= Linux seccomp 高级安全沙盒 =================
if IS_LINUX:
    class sock_filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint)]
    class sock_fprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(sock_filter))]
    
    BPF_LD, BPF_W, BPF_ABS = 0x00, 0x00, 0x20
    BPF_JEQ, BPF_K = 0x10, 0x00
    BPF_RET = 0x06
    SECCOMP_RET_KILL, SECCOMP_RET_ALLOW = 0x00000000, 0x7fff0000
    PR_SET_SECCOMP, SECCOMP_MODE_FILTER = 22, 2

    class SandboxSecurity:
        """系统级安全沙盒（基于 seccomp-bpf）"""
        def enable_high_security(self):
            print("[Security] Enabling High Security Level (seccomp-bpf)...")
            # 仅放行 read(0), write(1), exit(60), exit_group(231)
            filter_rules = [
                (BPF_LD | BPF_W | BPF_ABS, 0, 0, 0x00000000),
                (BPF_JEQ | BPF_K, 0, 5, 0),
                (BPF_JEQ | BPF_K, 0, 4, 1),
                (BPF_JEQ | BPF_K, 0, 3, 60),
                (BPF_JEQ | BPF_K, 0, 2, 231),
                (BPF_RET | BPF_K, 0, 0, SECCOMP_RET_KILL),
                (BPF_RET | BPF_K, 0, 0, SECCOMP_RET_ALLOW),
            ]
            filters = (sock_filter * len(filter_rules))()
            for i, (code, jt, jf, k) in enumerate(filter_rules):
                filters[i].code, filters[i].jt, filters[i].jf, filters[i].k = code, jt, jf, k
            prog = sock_fprog(len(filters), filters)
            
            if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(prog)) != 0:
                raise OSError("Failed to set seccomp filter (Requires root/CAP_SYS_ADMIN)")
            print("[Security] High Security Level ACTIVATED! Network & File I/O blocked.")
else:
    class SandboxSecurity:
        def enable_high_security(self):
            print("[Security] seccomp is Linux only. Skipping on this OS.")


# ================= 演示入口 =================
if __name__ == "__main__":
    print("=== 测试：线程本地存储(TLS)与反作弊内存池融合 ===\n")
    
    # 实例化全局控制器
    mem = GlobalMemoryController()
    sec = SandboxSecurity()

    # 1. 测试多线程 TLS 分配
    def worker(tid):
        print(f"[线程-{tid}] 正在分配内存...")
        ptrs = []
        for i in range(5):
            # 这里的 alloc 大部分是无锁的
            ptr = mem.alloc(128)
            ptrs.append(ptr)
            print(f"[线程-{tid}] 分配地址: {hex(ptr)}")
        
        # 模拟核心数据注册
        vital_ptr = mem.alloc(64)
        mem.register_vital(vital_ptr, 64)
        print(f"[线程-{tid}] 核心数据注册完成")

        # 释放回本地缓存
        for p in ptrs:
            mem.free(p)
        print(f"[线程-{tid}] 内存已释放回本地缓存")

    # 创建多个线程测试
    threads = []
    for i in range(3):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 2. 测试全局功能
    print("\n" + "="*50)
    print("=== 测试全局反作弊功能 ===")
    core_data = mem.alloc(256)
    mem.register_vital(core_data, 256)
    mem.drift() # 触发漂移

    # 3. 测试沙盒 (仅 Linux)
    if IS_LINUX:
        try:
            # 注意：开启后下面的 print 可能会报错（因为禁止了系统调用）
            # sec.enable_high_security()
            pass
        except Exception as e:
            print(f"沙盒开启失败 (通常需要 root): {e}")

    print("\n程序正常退出。")
