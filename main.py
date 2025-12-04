from PySide6.QtWidgets import QApplication

from petri_model import PetriNetModel
from petri_app import PetriNetApp
from petri_format import format_petri_to_text
from petri_logging import init_log


def main():
    """Точка входа в приложение моделирования сети Петри."""
    # Инициализируем лог (перезаписываем log.txt на новый запуск)
    init_log()

    # Для удобства создаём пример файла input.txt с случайно сгенерированной сетью
    initial_model = PetriNetModel(num_places=7, num_transitions=5)
    initial_model.generate_random_net()
    initial_model.generate_random_marking()
    try:
        with open("input.txt", "w", encoding="utf-8") as f:
            f.write(format_petri_to_text(initial_model))
    except Exception as e:
        print(f"Не удалось создать файл input.txt для примера: {e}")

    # Запуск Qt-приложения
    app = QApplication([])
    window = PetriNetApp()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()


