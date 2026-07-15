@echo off
REM ============================================================
REM pip 文件锁修复 — 管理员模式
REM ============================================================
REM 以管理员身份运行此脚本, 自动修复 pip 的 Windows Defender 文件锁问题
REM
REM 用法: 右键 → "以管理员身份运行"
REM ============================================================

cd /d "%~dp0.."

echo === pip 文件锁修复工具 (管理员模式) ===
echo.
echo 目标: D:\miniconda3\Lib\site-packages\pip\_internal\utils\filesystem.py
echo.

:: 备份原文件
copy /Y "D:\miniconda3\Lib\site-packages\pip\_internal\utils\filesystem.py" "%TEMP%\pip_filesystem.py.bak" >nul
echo [OK] 已备份到: %%TEMP%%\pip_filesystem.py.bak

:: 应用补丁
python scripts\fix-pip-lock.py

echo.
if %ERRORLEVEL% EQU 0 (
    echo === 完成 ===
    echo 提示: pip 升级后需重新运行此脚本。
) else (
    echo === 失败 ===
    echo 请手动修改 pip 源码。
)
pause
