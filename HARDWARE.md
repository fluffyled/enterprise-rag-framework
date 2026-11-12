# Проверенное оборудование

CPU: 12th Gen Intel(R) Core(TM) i5-12500H

RAM: 16 783 417 344 байт (около 15.6 GiB). GPU: NVIDIA GeForce RTX 3050 Laptop, 4096 MiB VRAM, драйвер 566.07.

Python 3.11 (отдельная .venv); системный Python 3.15 для ML не использован. Docker и Ollama не обнаружены. Используется portable llama.cpp CPU b12284, Tesseract 5.5.3.

## CUDA — проверено 12 ноября 2026

На D: установлены компоненты CUDA 12.6.3: nvcc 12.6.85, cudart, NVRTC, CCCL и NVML headers/libs. Путь: `tools/cuda/v12.6`. PyTorch в `.venv`: `2.6.0+cu126`. NVIDIA GeForce RTX 3050 Laptop GPU успешно выполнила проверку вычислений; NVRTC скомпилировал CUDA-ядро в PTX. `pip check` — без ошибок.

Перед работой выполнить `. .\project-env.ps1`: скрипт добавляет CUDA в PATH и направляет временные файлы и кеши на D:. Проверка: `.\.venv\Scripts\python.exe scripts/check_cuda.py`. Восстановление GPU-зависимостей: `.\.venv\Scripts\python.exe -m pip install -r requirements-cuda.txt`. Архивы NVIDIA проверены по SHA-256 из официального redistrib-манифеста; wheel PyTorch — по SHA-256 официального индекса.

Для обычной сборки CUDA C++ через nvcc дополнительно нужен MSVC/Visual Studio Build Tools; он не обнаружен. Для проверенных вычислений PyTorch и компиляции через NVRTC он не требуется. Выбор устройства в конкретных приложениях определяется их конфигурацией; установка CUDA сама по себе не меняет CPU-настройки моделей.
