@echo off
setlocal enabledelayedexpansion
REM Скрипт для сборки исполняемого файла

echo Установка PyInstaller...
pip install pyinstaller

echo Очистка предыдущих сборок...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Выберите тип сборки:
echo 1. Один exe файл с встроенным Graphviz
echo 2. Папка с файлами (классический вариант)
set /p choice="Введите 1 или 2: "

if "!choice!"=="1" (
    echo Сборка в один exe файл с Graphviz...
    pyinstaller build_exe_single.spec
    echo Сборка завершена
    echo Исполняемый файл находится в папке dist\PetriNetApp.exe
    echo Graphviz встроен в exe и работает из временной папки PyInstaller
) else (
    echo Сборка в папку...
    pyinstaller build_exe_folder.spec
    echo Сборка завершена
    echo Исполняемый файл находится в папке dist\PetriNetApp\PetriNetApp.exe
    echo ВАЖНО: Для установщика используйте эту версию (папка)
)

pause

