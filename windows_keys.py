from __future__ import annotations

import ctypes
from ctypes import wintypes


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                # ULONG_PTR is pointer-sized. Using POINTER(c_ulong) here can
                # make SendInput reject the structure with WinError 87 on x64.
                ("dwExtraInfo", wintypes.WPARAM)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", wintypes.WPARAM)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    # INPUT's size is determined by its largest union member (MOUSEINPUT).
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
)
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
user32.VkKeyScanW.restype = ctypes.c_short


VK = {
    "backspace": 0x08, "tab": 0x09, "return": 0x0D, "enter": 0x0D,
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12, "pause": 0x13,
    "caps_lock": 0x14, "escape": 0x1B, "space": 0x20, "prior": 0x21,
    "next": 0x22, "end": 0x23, "home": 0x24, "left": 0x25, "up": 0x26,
    "right": 0x27, "down": 0x28, "insert": 0x2D, "delete": 0x2E,
    "win": 0x5B, "menu": 0x5D, "num_lock": 0x90, "scroll_lock": 0x91,
}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})


def _vk_for(key: str) -> int:
    if key in VK:
        return VK[key]
    if len(key) == 1:
        result = user32.VkKeyScanW(key)
        if result == -1:
            raise ValueError(f"Key is not available on the current keyboard layout: {key}")
        return result & 0xFF
    raise ValueError(f"Unsupported key: {key}")


def _send(vk: int, up: bool = False) -> None:
    item = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0))
    if user32.SendInput(1, ctypes.byref(item), ctypes.sizeof(INPUT)) != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def send_shortcut(keys: list[str]) -> None:
    vks = [_vk_for(key) for key in keys]
    try:
        for vk in vks:
            _send(vk)
    finally:
        for vk in reversed(vks):
            _send(vk, True)


def foreground_executable() -> str:
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return path.value
    finally:
        kernel32.CloseHandle(handle)
    return ""
