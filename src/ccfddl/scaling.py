"""Size the interface to the screen.

Qt reads its scale factor once, when the QApplication is created, so the
factor is chosen beforehand from the primary monitor and applied through the
QT_SCALE_FACTOR environment variable. Changing it needs a restart. The
collapsed pill is enlarged a little more than the rest, so it stays easy to
read without the expanded panel getting too big.
"""

import ctypes
import os
import subprocess
import sys

REFERENCE_HEIGHT = 1000  # logical pixels; taller screens get a proportionally larger interface
SCALE_CHOICES = (1.0, 1.25, 1.5, 1.75, 2.0)
PANEL_GROWTH = 0.7  # the expanded panel grows 70% as much as the pill, e.g. 135% at a 150% setting
_applied = False  # True when QT_SCALE_FACTOR was set here rather than by the user
_pill_factor = 1.0


def panel_scale(scale: float) -> float:
    return 1 + (scale - 1) * PANEL_GROWTH


def pill_factor() -> float:
    """Extra enlargement for the collapsed pill on top of Qt's (panel) scale factor."""
    return _pill_factor


def auto_scale(logical_height: int | None) -> float:
    """Keep the widget at a similar share of the screen height, in steps of 25%."""
    if not logical_height:
        return 1.0
    return min(max(round(logical_height / REFERENCE_HEIGHT * 4) / 4, SCALE_CHOICES[0]), SCALE_CHOICES[-1])


def primary_logical_height() -> int | None:
    """Height of the primary monitor in pixels at its Windows display scaling (e.g. 1440 at 150% → 960)."""
    if sys.platform != 'win32':
        return None
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                    ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]

    try:
        user32, shcore = ctypes.WinDLL('user32'), ctypes.WinDLL('shcore')
        user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.MonitorFromPoint.restype = wintypes.HMONITOR
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
        shcore.GetDpiForMonitor.argtypes = [wintypes.HMONITOR, ctypes.c_int,
                                            ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT)]
        # Per-monitor aware for this thread only, so Qt can still set the process awareness later.
        previous = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        try:
            monitor = user32.MonitorFromPoint(wintypes.POINT(0, 0), 1)  # MONITOR_DEFAULTTOPRIMARY
            info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
            dpi_x, dpi_y = wintypes.UINT(), wintypes.UINT()
            if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)) or \
                    shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) != 0:
                return None
        finally:
            if previous:
                user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(previous))
        return round((info.rcMonitor.bottom - info.rcMonitor.top) * 96 / dpi_y.value)
    except (OSError, AttributeError):
        return None


def apply_scale(preferred: float | None) -> float:
    """Set the interface size; ``None`` picks one for the primary screen. A user-set variable wins.

    ``scale`` is the pill's size. Qt's factor, which sizes everything else, is the smaller panel scale.
    """
    global _applied, _pill_factor
    if 'QT_SCALE_FACTOR' in os.environ and not _applied:
        return float(os.environ['QT_SCALE_FACTOR'])
    scale = preferred if preferred is not None else auto_scale(primary_logical_height())
    panel = panel_scale(scale)
    os.environ['QT_SCALE_FACTOR'] = f'{panel:g}'
    _pill_factor = scale / panel
    _applied = True
    return scale


def restart():
    """Start a fresh copy of the program, which picks up the saved scale; the caller then quits."""
    environment = dict(os.environ)
    if _applied:
        environment.pop('QT_SCALE_FACTOR', None)
    # A one-file executable must not reuse this process's unpacked files, which go when it exits.
    environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    if getattr(sys, 'frozen', False):
        command = [sys.executable, *sys.argv[1:]]
    else:
        command = [sys.executable, os.path.abspath(sys.argv[0]), *sys.argv[1:]]
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    subprocess.Popen(command, env=environment, creationflags=flags, close_fds=True)
