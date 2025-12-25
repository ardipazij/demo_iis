# Быстрая инструкция по сборке (Windows)

## 1. Установите зависимости
```bash
pip install pyinstaller
```

## 2. Запустите сборку
```bash
build.bat
```
Скрипт предложит выбрать:
- **Вариант 1**: ✅ **Один exe файл с встроенным Graphviz** (автоматическая распаковка при первом запуске)
- **Вариант 2**: Папка с файлами (классический вариант)

Или вручную:
```bash
# Для одного exe с Graphviz (РЕКОМЕНДУЕТСЯ):
pyinstaller build_exe_single.spec

# Для папки:
pyinstaller build_exe_folder.spec
```

## 3. Проверьте результат
- **Один exe**: `dist\PetriNetApp.exe` ✅ (Graphviz распакуется при первом запуске)
- **Папка**: `dist\PetriNetApp\PetriNetApp.exe`

## 4. Создайте установщик

### Для одного exe файла:
1. Установите [Inno Setup](https://jrsoftware.org/isdl.php)
2. Откройте `setup_single.iss` в Inno Setup Compiler
3. Нажмите F9 (Compile)
4. Установщик: `installer\PetriNetApp_Setup_Single.exe`

### Для папки:
1. Откройте `setup.iss` в Inno Setup Compiler
2. Нажмите F9 (Compile)
3. Установщик: `installer\PetriNetApp_Setup.exe`

## Важно!
- ✅ **Рекомендуется вариант 1** (один exe) - Graphviz встроен прямо в exe, работает из временной папки PyInstaller
- Перед сборкой убедитесь, что папка `Graphviz-14.1.1-win32` находится в `demo_iis\`
- Размер одного exe будет ~150-250 МБ (это нормально для PySide6 + Graphviz + все зависимости)
- Graphviz работает прямо из exe, **ничего не распаковывается** - все в одном файле!
- Тестируйте exe перед созданием установщика!
- При установке создастся папка `saved_layouts` для сохранений пользователя

