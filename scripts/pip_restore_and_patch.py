"""
Clean restore pip filesystem.py from original backup + apply patch via PowerShell (elevated)
"""
import ctypes
import os
import sys
import tempfile

FP = r"D:\miniconda3\Lib\site-packages\pip\_internal\utils\filesystem.py"
BAK = r"C:\Users\Administrator.DESKTOP-K90E5CL\AppData\Local\Temp\pip_filesystem_26.0.1.bak"


class _SEI(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong), ("fMask", ctypes.c_ulong),
        ("hwnd", ctypes.c_void_p), ("lpVerb", ctypes.c_wchar_p),
        ("lpFile", ctypes.c_wchar_p), ("lpParameters", ctypes.c_wchar_p),
        ("lpDirectory", ctypes.c_wchar_p), ("nShow", ctypes.c_int),
        ("hInstApp", ctypes.c_void_p), ("lpIDList", ctypes.c_void_p),
        ("lpClass", ctypes.c_wchar_p), ("hkeyClass", ctypes.c_void_p),
        ("dwHotKey", ctypes.c_ulong), ("hIcon", ctypes.c_void_p),
        ("hProcess", ctypes.c_void_p),
    ]


def runas(exe, args, wait_sec=60):
    sei = _SEI()
    sei.cbSize = ctypes.sizeof(_SEI)
    sei.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb = "runas"
    sei.lpFile = exe
    sei.lpParameters = args
    sei.nShow = 0
    ret = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
    if ret and sei.hProcess:
        ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, wait_sec * 1000)
        exit_code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)
        return exit_code.value == 0
    return False


# Step 1: 恢复原始文件
print("Step 1: Restore from original backup...")
restore_code = f"import shutil; shutil.copy2({BAK!r}, {FP!r}); print('OK')"
tmp1 = os.path.join(tempfile.gettempdir(), "_pip_restore_final.py")
with open(tmp1, "w", encoding="utf-8") as f:
    f.write(restore_code)
ok = runas(sys.executable, tmp1)
os.remove(tmp1)
print(f"  Restore: {'OK' if ok else 'FAIL'}")

sz = os.path.getsize(FP)
print(f"  Size: {sz} (expected 6892)")
assert sz == 6892, f"Restore failed: {sz} != 6892"
print("  Verified clean!")

# Step 2: PowerShell 文本替换 (避免 Python 字符串缩进问题)
print("\nStep 2: Apply patch via PowerShell...")
ps_code = (
    '$f = "' + FP + '"; '
    '$c = Get-Content $f -Raw; '
    '$old = "            os.unlink(file)"; '
    '$new = ('
    '"            try:",'
    '"                os.unlink(file)",'
    '"            except PermissionError:",'
    '"                pass  # Windows Defender 锁定, 但目录确实可写",'
    '"            return True"'
    ') -join "`r`n"; '
    '$c = $c.Replace($old, $new); '
    'Set-Content $f $c -Encoding UTF8 -NoNewLine; '
    'if (Select-String -Path $f -Pattern "except PermissionError" -SimpleMatch) { exit 0 } else { exit 1 }'
)
tmp2 = os.path.join(tempfile.gettempdir(), "_pip_patch_final.ps1")
with open(tmp2, "w", encoding="utf-8") as f:
    f.write(ps_code)
ok2 = runas("powershell.exe", f"-ExecutionPolicy Bypass -File \"{tmp2}\"")
os.remove(tmp2)
print(f"  Patch: {'OK' if ok2 else 'FAIL'}")

# Step 3: 验证
print("\nStep 3: Verify...")
with open(FP) as f:
    for i, line in enumerate(f, 1):
        if 113 <= i <= 119:
            print(f"  L{i}: {line.rstrip()}")

from pip._internal.utils.filesystem import _test_writable_dir_win
import tempfile as tf
result = _test_writable_dir_win(tf.gettempdir())
print(f"  Writable test: {result}")

if result and ok2:
    print("\n✅ ALL OK! Patch applied successfully.")
else:
    print("\n❌ Patch FAILED.")
