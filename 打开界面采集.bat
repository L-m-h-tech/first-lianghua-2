@echo off
chcp 65001 >nul
rem 常驻运行界面操作收集装置（Ctrl+C 停止）。
rem 请先手动打开 Legend（推荐用『Legend 调试模式.bat』并登录模拟账号）与同花顺期货通。
cd /d "%~dp0"
"D:\Python\python.exe" run.py --daemon
pause