@echo off
chcp 65001 >nul
echo 正在启动 Celery Worker（Windows 优化模式）...
echo.

:: 设置环境变量限制资源使用
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1

:: 使用 solo 模式启动（单进程，适合 Windows 开发环境）
celery -A celery_worker worker --pool=solo --loglevel=info --concurrency=1

pause
