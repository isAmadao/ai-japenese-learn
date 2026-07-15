"""
pip 文件锁修复脚本 — Windows Defender 兼容补丁
===============================================

问题: Windows Defender 实时扫描锁定新文件, pip 的 _test_writable_dir_win()
     创建测试文件后 os.unlink() 失败 → 误判目录不可写 → pip install 失败

原理: 将 pip 源码中 os.unlink(file) 用 try/except PermissionError 包裹,
     让 pip 在文件被 Defender 锁定时也能正确判断"目录可写"

用法:
  python scripts/fix-pip-lock.py            # 打补丁
  python scripts/fix-pip-lock.py --undo     # 撤销补丁
  python scripts/fix-pip-lock.py --status   # 查看状态
  python scripts/fix-pip-lock.py --defender # 添加 Defender 排除 (需管理员)
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

# 目标文件路径 (硬编码, 避免 import pip 时因文件损坏而失败)
PIP_FILESYSTEM_PY = (
    "D:/miniconda3/Lib/site-packages/pip/_internal/utils/filesystem.py"
)

# 替换规则 — 包含上下文以避免 16-space 的 os.unlink 误匹配 12-space 模式
ORIGINAL_SNIPPET = "            os.unlink(file)\n            return True"
PATCHED_SNIPPET = textwrap.dedent("""\
            try:
                os.unlink(file)
            except PermissionError:
                pass  # Windows Defender 锁定, 但目录确实可写
            return True""")


# ============================================================
#  文件操作
# ============================================================

def read_file(path: str = PIP_FILESYSTEM_PY) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def write_file(path: str, content: str) -> bool:
    """直接写入, 失败返回 False (通常因权限不足)"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except PermissionError:
        return False


def backup_to_temp(path: str) -> str | None:
    """备份到用户临时目录"""
    bak = os.path.join(tempfile.gettempdir(), "pip_filesystem.py.bak")
    try:
        shutil.copy2(path, bak)
        return bak
    except OSError:
        return None


# ============================================================
#  补丁逻辑
# ============================================================

def check_patched(content: str) -> bool:
    """检查 os.unlink(file) 是否已被 try/except 包裹"""
    return (
        "try:\n                os.unlink(file)\n            except PermissionError:\n"
        in content and ORIGINAL_SNIPPET not in content
    )


def make_patched_content(content: str) -> str | None:
    """将 content 中的 os.unlink 替换为 try/except, 返回新内容"""
    if ORIGINAL_SNIPPET not in content:
        return None
    return content.replace(ORIGINAL_SNIPPET, PATCHED_SNIPPET, 1)


def make_unpatched_content(content: str) -> str | None:
    """将 try/except 块还原为 os.unlink 单行"""
    if check_patched(content):
        return content.replace(PATCHED_SNIPPET, ORIGINAL_SNIPPET, 1)
    return None


# ============================================================
#  提权执行 (ShellExecuteExW runas + PowerShell)
# ============================================================

def _elevate_powershell(ps_code: str, timeout_sec: int = 60) -> bool:
    """以管理员身份执行一段 PowerShell 代码

    使用 ctypes ShellExecuteExW + runas 动词启动 PowerShell,
    适用于需要管理员权限的文件写入场景。
    """
    import ctypes

    # 写入临时 .ps1 文件
    ps_file = os.path.join(tempfile.gettempdir(), "_pip_fix_elevate.ps1")
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(ps_code)

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

    sei = _SEI()
    sei.cbSize = ctypes.sizeof(_SEI)
    sei.fMask = 0x00000040
    sei.lpVerb = "runas"
    sei.lpFile = "powershell.exe"
    sei.lpParameters = f'-ExecutionPolicy Bypass -NoProfile -File "{ps_file}"'
    sei.nShow = 0

    result = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
    ok = False
    if result and sei.hProcess:
        ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, timeout_sec * 1000)
        exit_code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
        ok = exit_code.value == 0
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)

    try:
        os.remove(ps_file)
    except OSError:
        pass
    return ok


def apply_via_elevation():
    """通过提权应用补丁 (PowerShell 文本替换, 避免 Python 缩进问题)"""
    ps = (
        f'$f = "{PIP_FILESYSTEM_PY}"; '
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
        'if (Select-String -Path $f -Pattern "except PermissionError" -SimpleMatch) '
        '{exit 0} else {exit 1}'
    )
    print("  🔄 请求管理员权限 (UAC 弹窗, 请点击「是」)...")
    ok = _elevate_powershell(ps)
    if ok:
        print("  ✅ 提权补丁执行成功!")
    else:
        print("  ❌ 提权执行失败 (可能 UAC 被拒绝)")
    return ok


def restore_via_elevation():
    """通过提权恢复原始文件 (从备份)"""
    bak = os.path.join(tempfile.gettempdir(), "pip_filesystem.py.bak")
    if not os.path.exists(bak):
        old_bak = os.path.join(tempfile.gettempdir(), "pip_filesystem_26.0.1.bak")
        if os.path.exists(old_bak):
            bak = old_bak
        else:
            print(f"  ⚠️  备份文件不存在: {bak}")
            return False

    ps = f'Copy-Item "{bak}" "{PIP_FILESYSTEM_PY}" -Force; exit 0'
    print("  🔄 请求管理员权限恢复原始文件...")
    return _elevate_powershell(ps)


def add_defender_exclusion():
    """添加 Windows Defender 排除 (提权)"""
    conda_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.realpath(sys.executable)
    )))
    ps_code = (
        f'Start-Process powershell -ArgumentList '
        f'\'-Command\', \'Add-MpPreference -ExclusionPath "{conda_root}"\' '
        f'-Verb RunAs -Wait'
    )
    print(f"\n🛡️  添加 Windows Defender 排除项: {conda_root}")
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_code],
            capture_output=True, timeout=120,
        )
        print(f"  ✅ 已完成 (如果 UAC 被批准则排除项已添加)")
    except Exception as e:
        print(f"  ⚠️  出错: {e}")


# ============================================================
#  CLI
# ============================================================

def get_status_text(path: str = PIP_FILESYSTEM_PY) -> str:
    content = read_file(path)
    if content is None:
        return "读取失败"
    return "✅ 已应用" if check_patched(content) else "❌ 未应用"


def main():
    parser = argparse.ArgumentParser(
        description="修复 pip Windows Defender 文件锁问题",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            示例:
              python scripts/fix-pip-lock.py            # 打补丁
              python scripts/fix-pip-lock.py --status   # 查看状态
              python scripts/fix-pip-lock.py --undo     # 撤销
              python scripts/fix-pip-lock.py --defender # 添加 Defender 排除
        """),
    )
    parser.add_argument("--status", action="store_true", help="查看补丁状态")
    parser.add_argument("--undo", action="store_true", help="撤销补丁")
    parser.add_argument("--defender", action="store_true", help="添加 Windows Defender 排除项")
    args = parser.parse_args()

    # 文件存在性
    if not os.path.exists(PIP_FILESYSTEM_PY):
        print(f"❌ 文件不存在: {PIP_FILESYSTEM_PY}")
        sys.exit(1)

    pip_ver = "?"
    try:
        import pip
        pip_ver = pip.__version__
    except Exception:
        pass

    # --status
    if args.status:
        print(f"\n📋 pip filesystem.py: {PIP_FILESYSTEM_PY}")
        print(f"   补丁状态: {get_status_text()}")
        print(f"   pip 版本: {pip_ver}")
        return

    # --defender
    if args.defender:
        add_defender_exclusion()
        return

    # --undo
    if args.undo:
        print(f"\n🔧 撤销补丁")
        print(f"{'=' * 50}")
        content = read_file()
        if content is None:
            print(f"  ❌ 无法读取文件")
            sys.exit(1)
        if check_patched(content):
            print(f"  ⚠️  无法直接写入 (需要管理员权限)")
            print(f"  正在通过 PowerShell 提权还原...")
            restore_via_elevation()
            print(f"  状态: {get_status_text()}")
        else:
            print(f"  ⚠️  补丁未应用, 无需撤销")
        return

    # 默认: 打补丁
    print(f"\n🔧 pip 文件锁修复工具")
    print(f"{'=' * 50}")
    print(f"  pip 版本: {pip_ver}")
    print(f"  目标文件: {PIP_FILESYSTEM_PY}")
    print(f"  当前状态: {get_status_text()}")

    content = read_file()
    if content is None:
        print(f"  ❌ 无法读取文件")
        sys.exit(1)

    if check_patched(content):
        print(f"  ✅ 补丁已存在, 无需操作")
        return

    # 备份
    bak = backup_to_temp(PIP_FILESYSTEM_PY)
    if bak:
        print(f"  📦 已备份到: {bak}")

    # 尝试直接写入
    new_content = make_patched_content(content)
    if new_content is None:
        print(f"  ❌ 未找到目标行 '{ORIGINAL_SNIPPET}'!")
        print(f"     pip 版本可能已变更, 请手动检查文件")
        sys.exit(1)

    if write_file(PIP_FILESYSTEM_PY, new_content):
        print(f"  ✅ 补丁成功!")
        print(f"  状态: {get_status_text()}")
        return

    # 需要提权
    print(f"  ⚠️  无法直接写入 (需要管理员权限)")
    print(f"  正在尝试 UAC 弹窗提权...")
    ok = apply_via_elevation()
    if ok:
        print(f"  状态: {get_status_text()}")
    else:
        print(f"  ❌ 提权失败。请在 **管理员 PowerShell** 中手动运行:")
        print(f"")
        print(f"     python scripts/fix-pip-lock.py")
        print(f"")
        print(f"   或在管理员 PowerShell 中执行:")
        print(f"")
        print(f"     `$content = Get-Content '{PIP_FILESYSTEM_PY}' -Raw")
        print(f"     `$old = '            os.unlink(file)'")
        print(f"     `$new = @'")
        print(f"             try:")
        print(f"                 os.unlink(file)")
        print(f"             except PermissionError:")
        print(f"                 pass  # Windows Defender 锁定, 但目录确实可写")
        print(f"'@")
        print(f"     `$content = `$content.Replace(`$old, `$new)")
        print(f"     Set-Content '{PIP_FILESYSTEM_PY}' `$content -Encoding UTF8")

    print(f"\n💡 根治方案: 添加 Windows Defender 排除 (需管理员)")
    print(f"     python scripts/fix-pip-lock.py --defender")


if __name__ == "__main__":
    main()
