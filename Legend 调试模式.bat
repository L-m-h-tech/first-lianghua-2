@echo off
chcp 65001 >nul
rem 以调试模式启动 OpenVLab Legend（端口 9225），供界面操作收集装置 CDP 读取。
rem 请手动双击本文件启动后，在 Legend 内完成模拟账号登录。
start "" "E:\OpendVlab Legend\openvlab-legend\OpenVlab Legend.exe" --remote-debugging-port=9225 --remote-allow-origins=*
echo Legend 已以调试模式启动（CDP 端口 9225）。
echo 请在弹出的 Legend 中完成登录后，运行装置：D:\Python\python.exe run.py --probe --legend
timeout /t 5 >nul