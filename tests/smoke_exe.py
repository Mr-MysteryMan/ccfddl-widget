"""Unattended Windows startup probe for the actual one-file executable."""
import ctypes
from ctypes import wintypes
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('executable', nargs='?', default='dist/CCFDDLWidget.exe')
args = parser.parse_args()
if sys.platform != 'win32':
    parser.error('This startup check requires Windows.')
executable = Path(args.executable).resolve()
if not executable.is_file():
    parser.error(f'Executable not found: {executable}')

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
               ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
               ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
               ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
               ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260)]

kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
user32.EnumWindows.argtypes = [CALLBACK, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, CALLBACK, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]

def descendants(pid):
    snapshot = kernel32.CreateToolhelp32Snapshot(2, 0)
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    processes = []
    success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
    while success:
        processes.append((entry.th32ProcessID, entry.th32ParentProcessID))
        success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    kernel32.CloseHandle(snapshot)
    result = {pid}
    for _ in range(10):
        updated = result | {child for child, parent in processes if parent in result}
        if updated == result:
            break
        result = updated
    return result

def text(hwnd):
    buffer = ctypes.create_unicode_buffer(8192)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value

def window_info(pids):
    windows = []
    @CALLBACK
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids:
            classname = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, classname, 256)
            children = []
            @CALLBACK
            def child(child_hwnd, _):
                value = text(child_hwnd)
                if value:
                    children.append(value)
                return True
            user32.EnumChildWindows(hwnd, child, 0)
            windows.append({'hwnd': hwnd, 'title': text(hwnd), 'class': classname.value,
                            'visible': bool(user32.IsWindowVisible(hwnd)), 'children': children})
        return True
    user32.EnumWindows(visit, 0)
    return windows

process = subprocess.Popen([str(executable)], cwd=executable.parent,
                           creationflags=subprocess.CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.monotonic() + 20
observed = []
verdict = 'TIMEOUT'
visible_since = None
try:
    while time.monotonic() < deadline:
        pids = descendants(process.pid)
        observed = window_info(pids)
        errors = [w for w in observed if 'Unhandled exception' in w['title'] or
                  any('DLL load failed' in value for value in w['children'])]
        if errors:
            verdict = 'FAIL'
            break
        widgets = [w for w in observed if w['visible'] and w['class'].startswith('Qt')
                   and 'QWindow' in w['class'] and w['title'] == 'CCFDDLWidget']
        if widgets:
            visible_since = visible_since or time.monotonic()
            if time.monotonic() - visible_since >= 2:
                verdict = 'PASS'
                break
        else:
            visible_since = None
        if process.poll() is not None:
            verdict = f'EXIT {process.returncode}'
            break
        time.sleep(0.1)
finally:
    report = {'verdict': verdict, 'pid': process.pid, 'windows': observed}
    print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
    pids = descendants(process.pid)
    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print('Unable to close the startup-check process; close its window manually.', file=sys.stderr)
sys.exit(0 if verdict == 'PASS' else 1)
