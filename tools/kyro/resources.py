"""Conservative Windows build concurrency based on currently available memory."""
import ctypes
import os

def worker_budget(requested):
    if os.name != 'nt': return requested

    class MemoryStatus(ctypes.Structure):
        _fields_ = [('length',ctypes.c_ulong),('load',ctypes.c_ulong),
                    ('total_physical',ctypes.c_ulonglong),('available_physical',ctypes.c_ulonglong),
                    ('total_page',ctypes.c_ulonglong),('available_page',ctypes.c_ulonglong),
                    ('total_virtual',ctypes.c_ulonglong),('available_virtual',ctypes.c_ulonglong),
                    ('available_extended',ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError('Unable to inspect available memory')
    available_gib = status.available_physical/1024**3
    workers = max(1,min(requested,int((available_gib-2)/3)))
    print(f'Available memory: {available_gib:.1f} GiB; using {workers} build worker(s).',flush=True)
    return workers
