"""
Модуль для настройки Graphviz из встроенных ресурсов PyInstaller.
Использует Graphviz прямо из временной папки _MEIPASS без распаковки.
"""
import os
import sys
from pathlib import Path


def get_graphviz_path():
    """
    Получает путь к Graphviz из ресурсов PyInstaller.
    Graphviz уже встроен в exe и доступен через _MEIPASS.
    """
    if getattr(sys, 'frozen', False):
        # Запущено из exe - используем временную папку PyInstaller
        if hasattr(sys, '_MEIPASS'):
            graphviz_bin = Path(sys._MEIPASS) / "graphviz_bin"
            if graphviz_bin.exists() and (graphviz_bin / "dot.exe").exists():
                return str(graphviz_bin)
    else:
        # Запущено из скрипта - ищем локально
        possible_paths = [
            Path(__file__).parent / "Graphviz-14.1.1-win32" / "bin",
            Path.cwd() / "Graphviz-14.1.1-win32" / "bin",
        ]
        
        for path in possible_paths:
            if path.exists() and (path / "dot.exe").exists():
                return str(path)
    
    return None


def setup_graphviz_path():
    """Настраивает PATH для Graphviz из встроенных ресурсов."""
    graphviz_path = get_graphviz_path()
    
    if graphviz_path:
        # Добавляем в PATH
        if graphviz_path not in os.environ.get("PATH", ""):
            os.environ["PATH"] = graphviz_path + os.pathsep + os.environ.get("PATH", "")
        
        # Устанавливаем переменную окружения для pydot
        graphviz_install_dir = str(Path(graphviz_path).parent)
        os.environ["GRAPHVIZ_INSTALL_DIR"] = graphviz_install_dir
        
        return graphviz_path
    
    return None

