@echo off
REM pip 文件锁修复脚本 — Windows Defender 兼容补丁
REM 用法:
REM   scripts\fix-pip-lock             打补丁
REM   scripts\fix-pip-lock --status    查看状态
REM   scripts\fix-pip-lock --undo      撤销
REM   scripts\fix-pip-lock --defender  添加 Defender 排除

cd /d "%~dp0.."
python scripts\fix-pip-lock.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo 如果自动修复失败, 请以管理员身份运行:
    echo   1. 右键点击 Windows 开始菜单 → "Windows PowerShell (管理员)"
    echo   2. cd %cd%
    echo   3. python scripts\fix-pip-lock.py
    pause
)
