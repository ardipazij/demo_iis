"""
Модуль для сохранения и загрузки размещений графов Петри.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF


def get_user_data_dir() -> Path:
    """
    Возвращает путь к пользовательской директории для сохранения данных.
    Использует AppData\Local для Windows, чтобы избежать проблем с правами доступа.
    """
    if os.name == 'nt':  # Windows
        appdata = os.getenv('LOCALAPPDATA')
        if appdata:
            return Path(appdata) / "PetriNetApp" / "saved_layouts"
        else:
            # Fallback на домашнюю директорию
            return Path.home() / "PetriNetApp" / "saved_layouts"
    else:
        # Linux/Mac
        return Path.home() / ".petrinetapp" / "saved_layouts"


class PetriNetSave:
    """Класс для сохранения и загрузки размещений графов Петри."""
    
    def __init__(self, save_dir: str = None):
        """
        Инициализирует менеджер сохранений.
        
        Args:
            save_dir: Путь к директории сохранений. Если None, используется
                     пользовательская директория (AppData для Windows).
        """
        if save_dir is None:
            self.save_dir = get_user_data_dir()
        else:
            self.save_dir = Path(save_dir)
        
        # Создаем директорию, если её нет
        if not self.save_dir.exists():
            self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # Преобразуем в строку для совместимости
        self.save_dir = str(self.save_dir)
    
    def save_layout(self, name: str, model, place_positions: List[QPointF], 
                    transition_positions: List[QPointF], layout_mode: str) -> bool:
        """
        Сохраняет размещение графа.
        
        Args:
            name: Имя сохранения
            model: Модель сети Петри
            place_positions: Список позиций мест
            transition_positions: Список позиций переходов
            layout_mode: Тип размещения
            
        Returns:
            True если успешно сохранено
        """
        try:
            data = {
                "name": name,
                "model": {
                    "P": model.P,
                    "T": model.T,
                    "M": model.M,
                    "W_in": model.W_in,
                    "W_out": model.W_out,
                    "MAX_TOKENS": model.MAX_TOKENS
                },
                "place_positions": [
                    {"x": float(pos.x()), "y": float(pos.y())} 
                    for pos in place_positions
                ],
                "transition_positions": [
                    {"x": float(pos.x()), "y": float(pos.y())} 
                    for pos in transition_positions
                ],
                "layout_mode": layout_mode
            }
            
            filename = os.path.join(self.save_dir, f"{name}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Ошибка при сохранении: {e}")
            return False
    
    def save_graph(self, name: str, model) -> bool:
        """
        Сохраняет только граф (модель) без размещения.
        
        Args:
            name: Имя сохранения
            model: Модель сети Петри
            
        Returns:
            True если успешно сохранено
        """
        try:
            data = {
                "name": name,
                "type": "graph_only",
                "model": {
                    "P": model.P,
                    "T": model.T,
                    "M": model.M,
                    "W_in": model.W_in,
                    "W_out": model.W_out,
                    "MAX_TOKENS": model.MAX_TOKENS
                }
            }
            
            filename = os.path.join(self.save_dir, f"{name}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Ошибка при сохранении: {e}")
            return False
    
    def load_layout(self, name: str) -> Optional[Dict]:
        """
        Загружает сохраненное размещение.
        
        Args:
            name: Имя сохранения
            
        Returns:
            Словарь с данными или None если ошибка
        """
        try:
            filename = os.path.join(self.save_dir, f"{name}.json")
            if not os.path.exists(filename):
                return None
            
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Преобразуем позиции обратно в QPointF
            if "place_positions" in data:
                data["place_positions"] = [
                    QPointF(pos["x"], pos["y"]) 
                    for pos in data["place_positions"]
                ]
            if "transition_positions" in data:
                data["transition_positions"] = [
                    QPointF(pos["x"], pos["y"]) 
                    for pos in data["transition_positions"]
                ]
            
            return data
        except Exception as e:
            print(f"Ошибка при загрузке: {e}")
            return None
    
    def list_saved(self) -> List[str]:
        """
        Возвращает список всех сохраненных размещений.
        
        Returns:
            Список имен сохранений
        """
        try:
            files = [f for f in os.listdir(self.save_dir) if f.endswith('.json')]
            names = [os.path.splitext(f)[0] for f in files]
            return sorted(names)
        except Exception as e:
            print(f"Ошибка при получении списка: {e}")
            return []
    
    def delete_saved(self, name: str) -> bool:
        """
        Удаляет сохраненное размещение.
        
        Args:
            name: Имя сохранения
            
        Returns:
            True если успешно удалено
        """
        try:
            filename = os.path.join(self.save_dir, f"{name}.json")
            if os.path.exists(filename):
                os.remove(filename)
                return True
            return False
        except Exception as e:
            print(f"Ошибка при удалении: {e}")
            return False

