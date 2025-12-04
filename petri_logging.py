import datetime
import atexit

from petri_model import PetriNetModel
from petri_format import format_petri_to_text

LOG_FILE = "log.txt"


def init_log() -> None:
    """Очищает/создаёт файл логов для нового запуска программы."""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] Запуск приложения моделирования сети Петри\n")
    except OSError:
        # Лог недоступен — не мешаем работе приложения
        pass


def log_event(message: str) -> None:
    """Добавляет строку в лог-файл с временной меткой."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except OSError:
        # Лог недоступен — не мешаем работе приложения
        pass


def log_state_snapshot(label: str, model: PetriNetModel) -> None:
    """Записывает в лог снимок текущего состояния сети Петри в табличном виде."""
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {label}\n")
            f.write(format_petri_to_text(model))
            f.write("\n")
    except OSError:
        # Лог недоступен — не мешаем работе приложения
        pass


def _log_on_exit() -> None:
    log_event("Приложение завершено.")


atexit.register(_log_on_exit)


