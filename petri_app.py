from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QHeaderView,
    QScrollArea,
    QSizePolicy,
    QComboBox,
)
from PySide6.QtCore import Qt

from petri_model import PetriNetModel
from petri_format import format_petri_to_text, parse_petri_from_text
from petri_logging import log_event, log_state_snapshot
from petri_widget import PetriNetWidget


class PetriNetApp(QMainWindow):
    """Главное окно Qt-приложения для моделирования сети Петри."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Моделирование Ординарной Сети Петри")
        self.setGeometry(100, 100, 800, 600)

        # Инициализация модели
        self.model = PetriNetModel(num_places=7, num_transitions=5)
        self.model.generate_random_net()
        self.model.generate_random_marking()

        self._setup_ui()
        self._update_display()
        # Синхронизируем ComboBox с текущим режимом
        self._sync_layout_combo()

    # --- Построение интерфейса ---

    def _setup_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)

        # Левая панель с кнопками
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_widget.setFixedWidth(220)

        # Виджет визуализации сети
        self.petri_view = PetriNetWidget(self.model)
        self.petri_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Табличный редактор сети
        self._init_editor_widgets()

        # Кнопки управления
        btn_load = QPushButton("1. Загрузить из файла")
        btn_load.clicked.connect(self._load_from_file)

        btn_random_marking = QPushButton("2. Случайная разметка")
        btn_random_marking.clicked.connect(self._random_marking)

        btn_random_net = QPushButton("3. Случайная сеть")
        btn_random_net.clicked.connect(self._random_net)

        btn_save = QPushButton("4. Выгрузить в output.txt")
        btn_save.clicked.connect(self._save_to_file)

        # Переключатель алгоритма раскладки (ComboBox)
        layout_label = QLabel("Раскладка:")
        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "Ряды",
            "Иерархия (демо)",
            "Конечный автомат",
            "Иерархический поток",
            "Инженерная схема",
            "Органический"
        ])
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)

        btn_step = QPushButton("5. Выполнить шаг (Сработать)")
        btn_step.clicked.connect(self._perform_step)

        controls_layout.addWidget(btn_load)
        controls_layout.addWidget(btn_random_marking)
        controls_layout.addWidget(btn_random_net)
        controls_layout.addWidget(btn_save)
        controls_layout.addWidget(layout_label)
        controls_layout.addWidget(self.layout_combo)
        controls_layout.addSpacing(20)
        controls_layout.addWidget(btn_step)
        controls_layout.addStretch(1)

        main_layout.addWidget(controls_widget)

        # Основная область с графом и таблицами
        # Граф сверху, таблицы снизу
        main_content = QVBoxLayout()
        main_content.addWidget(self.petri_view, stretch=3)
        
        # Область прокрутки для табличного редактора (внизу, всегда видима)
        self.editor_scroll = QScrollArea()
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setWidget(self.editor_widget)
        self.editor_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.editor_scroll.setMaximumHeight(300)  # Ограничиваем высоту, чтобы граф был виден
        self.editor_scroll.setMinimumHeight(200)  # Минимальная высота для видимости таблиц
        
        main_content.addWidget(self.editor_scroll, stretch=1)
        
        main_layout.addLayout(main_content, stretch=1)
        self.setCentralWidget(central_widget)

        # Заполнить таблицы начальными значениями
        self._sync_editor_from_model()

    # --- Табличный редактор ---

    def _init_editor_widgets(self):
        """Создает таблицы для ручного редактирования marking, W_in, W_out."""
        self.editor_widget = QWidget()
        layout = QVBoxLayout(self.editor_widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Разметка (M)
        lbl_marking = QLabel("Разметка мест M (0..3):")
        layout.addWidget(lbl_marking)
        self.table_marking = QTableWidget(1, self.model.P)
        self.table_marking.horizontalHeader().setVisible(True)
        self.table_marking.verticalHeader().setVisible(False)
        self.table_marking.setMinimumHeight(60)
        for i in range(self.model.P):
            self.table_marking.setHorizontalHeaderItem(i, QTableWidgetItem(f"p{i+1}"))
        header_m = self.table_marking.horizontalHeader()
        header_m.setStretchLastSection(False)
        header_m.setSectionResizeMode(QHeaderView.Interactive)
        header_m.setDefaultSectionSize(55)
        self.table_marking.verticalHeader().setDefaultSectionSize(32)
        layout.addWidget(self.table_marking)

        # Входная матрица W_in
        lbl_win = QLabel("Входная матрица W_in (0/1):")
        layout.addWidget(lbl_win)
        self.table_w_in = QTableWidget(self.model.T, self.model.P)
        self.table_w_in.horizontalHeader().setVisible(True)
        self.table_w_in.verticalHeader().setVisible(True)
        self.table_w_in.setMinimumHeight(5 * 32 + 40)
        for i in range(self.model.P):
            self.table_w_in.setHorizontalHeaderItem(i, QTableWidgetItem(f"p{i+1}"))
        for j in range(self.model.T):
            self.table_w_in.setVerticalHeaderItem(j, QTableWidgetItem(f"t{j+1}"))
        header_in = self.table_w_in.horizontalHeader()
        header_in.setStretchLastSection(False)
        header_in.setSectionResizeMode(QHeaderView.Interactive)
        header_in.setDefaultSectionSize(55)
        self.table_w_in.verticalHeader().setDefaultSectionSize(32)
        self.table_w_in.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table_w_in.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        layout.addWidget(self.table_w_in)

        # Выходная матрица W_out
        lbl_wout = QLabel("Выходная матрица W_out (0/1):")
        layout.addWidget(lbl_wout)
        self.table_w_out = QTableWidget(self.model.T, self.model.P)
        self.table_w_out.horizontalHeader().setVisible(True)
        self.table_w_out.verticalHeader().setVisible(True)
        self.table_w_out.setMinimumHeight(5 * 32 + 40)
        for i in range(self.model.P):
            self.table_w_out.setHorizontalHeaderItem(i, QTableWidgetItem(f"p{i+1}"))
        for j in range(self.model.T):
            self.table_w_out.setVerticalHeaderItem(j, QTableWidgetItem(f"t{j+1}"))
        header_out = self.table_w_out.horizontalHeader()
        header_out.setStretchLastSection(False)
        header_out.setSectionResizeMode(QHeaderView.Interactive)
        header_out.setDefaultSectionSize(55)
        self.table_w_out.verticalHeader().setDefaultSectionSize(32)
        self.table_w_out.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table_w_out.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        layout.addWidget(self.table_w_out)

        # Кнопка применения
        btn_apply = QPushButton("Применить изменения из таблиц")
        btn_apply.clicked.connect(self._apply_editor_to_model)
        layout.addWidget(btn_apply)

    def _sync_editor_from_model(self):
        """Заполняет таблицы значениями из текущей модели."""
        # marking
        for i in range(self.model.P):
            val = str(self.model.M[i])
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            self.table_marking.setItem(0, i, item)

        # W_in
        for t in range(self.model.T):
            for p in range(self.model.P):
                val = str(self.model.W_in[t][p])
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.table_w_in.setItem(t, p, item)

        # W_out
        for t in range(self.model.T):
            for p in range(self.model.P):
                val = str(self.model.W_out[t][p])
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.table_w_out.setItem(t, p, item)

    def _apply_editor_to_model(self):
        """Читает значения из таблиц, валидирует и записывает в модель."""
        try:
            # Разметка
            new_marking = []
            for i in range(self.model.P):
                item = self.table_marking.item(0, i)
                text = item.text().strip() if item is not None else "0"
                val = int(text)
                if val < 0 or val > self.model.MAX_TOKENS:
                    raise ValueError(
                        f"Разметка места p{i+1} должна быть в диапазоне 0..{self.model.MAX_TOKENS}."
                    )
                new_marking.append(val)

            # W_in
            new_w_in = [[0] * self.model.P for _ in range(self.model.T)]
            for t in range(self.model.T):
                for p in range(self.model.P):
                    item = self.table_w_in.item(t, p)
                    text = item.text().strip() if item is not None else "0"
                    val = int(text)
                    if val not in (0, 1):
                        raise ValueError(f"W_in[t{t+1}][p{p+1}] должно быть 0 или 1.")
                    new_w_in[t][p] = val

            # W_out
            new_w_out = [[0] * self.model.P for _ in range(self.model.T)]
            for t in range(self.model.T):
                for p in range(self.model.P):
                    item = self.table_w_out.item(t, p)
                    text = item.text().strip() if item is not None else "0"
                    val = int(text)
                    if val not in (0, 1):
                        raise ValueError(f"W_out[t{t+1}][p{p+1}] должно быть 0 или 1.")
                    new_w_out[t][p] = val

            # Дополнительная проверка связности переходов
            for name, mat in (("W_in", new_w_in), ("W_out", new_w_out)):
                for t_idx, row in enumerate(mat):
                    if sum(row) == 0:
                        raise ValueError(
                            f"Переход t{t_idx+1} в {name} не связан ни с одним местом (строка из одних нулей)."
                        )

            # Применяем к модели
            self.model.M = new_marking
            self.model.W_in = new_w_in
            self.model.W_out = new_w_out

            log_event("Модель изменена через табличный редактор (marking/W_in/W_out обновлены).")
            log_state_snapshot("Состояние сети после изменения через табличный редактор", self.model)
            # Сбрасываем раскладку при изменении модели
            self.petri_view.reset_layout()
            self._update_display()
        except ValueError as e:
            QMessageBox.critical(self, "Ошибка в таблицах", str(e))

    # --- Обновление отображения ---

    def _update_display(self, message: str = ""):
        """Обновляет визуализацию и таблицы."""
        # Обновляем визуализацию и редактор
        self.petri_view.update()
        self._sync_editor_from_model()
        
        # Показываем сообщение только если оно есть и важно
        if message and ("ошибка" in message.lower() or "блокирована" in message.lower()):
            QMessageBox.information(self, "Информация", message)

    # --- Слоты для кнопок ---

    def _load_from_file(self):
        """Загружает модель из выбранного пользователем текстового файла в табличном формате."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл с описанием сети Петри",
            "",
            "Текстовые файлы (*.txt);;Все файлы (*.*)",
        )
        if not file_name:
            return

        try:
            with open(file_name, "r", encoding="utf-8") as f:
                text = f.read()

            data = parse_petri_from_text(text, self.model.P, self.model.T, self.model.MAX_TOKENS)
            self.model.from_dict(data)
            log_event(f"Сеть загружена из файла '{file_name}'.")
            log_state_snapshot("Состояние сети после загрузки из файла", self.model)
            # Сбрасываем раскладку при загрузке новой модели
            self.petri_view.reset_layout()
            self._update_display()
        except FileNotFoundError:
            QMessageBox.critical(self, "Ошибка", f"Файл не найден:\n{file_name}")
        except ValueError as e:
            QMessageBox.critical(self, "Ошибка в данных сети", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Неожиданная ошибка", str(e))

    def _random_marking(self):
        """Заполнить случайными значениями (разметкой)."""
        self.model.generate_random_marking()
        log_event("Разметка M случайно перегенерирована (0..3).")
        log_state_snapshot("Состояние сети после генерации случайной разметки", self.model)
        # Сбрасываем раскладку при изменении разметки (хотя структура не меняется, но для консистентности)
        self.petri_view.reset_layout()
        self._update_display()

    def _random_net(self):
        """Сгенерировать случайную (но корректную) сеть Петри."""
        self.model.generate_random_net()
        log_event("Сгенерирована новая случайная ординарная сеть (W_in/W_out).")
        log_state_snapshot("Состояние сети после генерации новой случайной сети", self.model)
        # Сбрасываем раскладку при генерации новой сети
        self.petri_view.reset_layout()
        self._update_display()

    def _save_to_file(self):
        """Выгружает результат в output.txt в текстовом табличном формате."""
        try:
            with open("output.txt", "w", encoding="utf-8") as f:
                f.write(format_petri_to_text(self.model))
            log_event("Модель сети сохранена в файл 'output.txt'.")
            log_state_snapshot("Состояние сети на момент сохранения в output.txt", self.model)
            self._update_display()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл: {e}")

    def _perform_step(self):
        """Выполняет шаг работы (конкурентно и параллельно)."""
        result = self.model.step()
        log_event(f"Выполнен шаг моделирования. {result}")
        log_state_snapshot("Состояние сети после шага моделирования", self.model)
        
        # Показываем всплывающее сообщение только если сеть заблокирована
        if "заблокирована" in result.lower() or "нет разрешенных" in result.lower():
            QMessageBox.information(self, "Шаг выполнен", result)
        
        self._update_display()

    def _on_layout_changed(self, index):
        """Обработчик изменения режима раскладки через ComboBox."""
        mode_map = {
            0: "rows",
            1: "hier_demo",
            2: "fsm",
            3: "hierarchical",
            4: "orthogonal",
            5: "organic"
        }
        
        new_mode = mode_map.get(index, "rows")
        self.petri_view.set_layout_mode(new_mode)
        self._update_display()
    
    def _sync_layout_combo(self):
        """Синхронизирует ComboBox с текущим режимом раскладки."""
        mode_to_index = {
            "rows": 0,
            "hier_demo": 1,
            "fsm": 2,
            "hierarchical": 3,
            "orthogonal": 4,
            "organic": 5
        }
        current_mode = self.petri_view.layout_mode
        index = mode_to_index.get(current_mode, 0)
        self.layout_combo.setCurrentIndex(index)


