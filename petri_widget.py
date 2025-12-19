from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from PySide6.QtCore import Qt, QPointF
import math

# Попытка импортировать networkx и pydot для продвинутых алгоритмов размещения
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    import pydot
    HAS_PYDOT = True
except ImportError:
    HAS_PYDOT = False


class PetriNetWidget(QWidget):
    """
    Простой виджет визуализации ординарной сети Петри.

    - места (P) рисуются как круги
    - переходы (T) рисуются как прямоугольники
    - дуги из W_in / W_out — как стрелки
    - фишки (маркировка) — маленькие чёрные кружки внутри мест (до 3 шт.)
    """

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)

        # Предрасчёт простой схемы расположения:
        # 7 мест в верхнем ряду, 5 переходов в нижнем ряду.
        self.place_positions = []
        self.transition_positions = []
        # layout_mode: "rows" (по рядам, как раньше) или "hier_demo" (условно иерархический вид)
        self.layout_mode = "rows"
        
        # Для перетаскивания
        self.dragging = False
        self.selected_place_idx = None
        self.selected_transition_idx = None
        self.drag_start_pos = None
        
        # Флаг, указывающий что позиции были установлены (не нужно пересчитывать при resize)
        self.positions_initialized = False
        
        # Сохраненный масштаб для предотвращения увеличения графа
        self._last_scale = None
        self._last_widget_size = None  # Для отслеживания изменения размера виджета
        
        # Для ортогонального режима: контрольные точки для ломаных линий
        self.orthogonal_arc_points = {}  # {(p_idx, t_idx): [QPointF, ...]} или {(t_idx, p_idx): [QPointF, ...]}
        
        # Базовые размеры элементов (будут масштабироваться)
        self.base_place_radius = 18
        self.base_trans_width = 24
        self.base_trans_height = 60

    def set_layout_mode(self, mode: str):
        """Позволяет сменить режим раскладки и перерисовать виджет."""
        if mode not in ("rows", "hier_demo", "fsm"):
            return
        self.layout_mode = mode
        # Сбрасываем позиции при смене режима, чтобы применить новую раскладку
        self.place_positions = []
        self.transition_positions = []
        self.positions_initialized = False
        self.update()

    def set_model(self, model):
        """Позволяет заменить модель (если её перезагружают)."""
        self.model = model
        # Сбрасываем позиции при смене модели
        self.reset_layout()

    def reset_layout(self):
        """Сбрасывает раскладку и пересчитывает позиции элементов."""
        # Сбрасываем позиции
        self.place_positions = []
        self.transition_positions = []
        self.positions_initialized = False
        # Сбрасываем сохраненный масштаб и размер виджета
        self._last_scale = None
        self._last_widget_size = None
        # Перерисовываем виджет
        self.update()

    # --- Геометрия ---

    def _compute_layout(self):
        """Рассчитывает координаты мест и переходов в зависимости от размера виджета."""
        if self.model is None:
            return self.base_place_radius, self.base_trans_width, self.base_trans_height

        # Вычисляем динамические размеры на основе доступного пространства
        place_radius, trans_width, trans_height = self._calculate_dynamic_sizes()

        # ВАЖНО: Если идет перетаскивание, НЕ пересчитываем позиции для ЛЮБОГО режима
        if self.dragging:
            return place_radius, trans_width, trans_height

        # Пересчитываем позиции только если они не инициализированы или изменилось количество элементов
        should_recompute = (
            not self.positions_initialized or
            not self.place_positions or 
            not self.transition_positions or 
            len(self.place_positions) != self.model.P or 
            len(self.transition_positions) != self.model.T
        )
        
        if should_recompute:
            self.place_positions = []
            self.transition_positions = []
            # Выбор алгоритма раскладки
            if self.layout_mode == "fsm":
                self._compute_layout_fsm(place_radius, trans_width, trans_height)
            elif self.layout_mode == "hierarchical":
                self._compute_layout_hierarchical(place_radius, trans_width, trans_height)
            elif self.layout_mode == "orthogonal":
                self._compute_layout_orthogonal(place_radius, trans_width, trans_height)
            elif self.layout_mode == "organic":
                self._compute_layout_organic(place_radius, trans_width, trans_height)
            elif (
                self.layout_mode == "hier_demo"
                and self.model.P >= 7
                and self.model.T >= 5
            ):
                self._compute_layout_hier_demo(place_radius, trans_width, trans_height)
            else:
                self._compute_layout_rows(place_radius, trans_width, trans_height)
            self.positions_initialized = True
            # Сохраняем размер виджета после инициализации
            self._last_widget_size = (self.width(), self.height())
        elif self.layout_mode == "fsm" and self.positions_initialized:
            # Для FSM пересчитываем ТОЛЬКО при изменении размера виджета (если не идет перетаскивание)
            current_size = (self.width(), self.height())
            if self._last_widget_size is not None and current_size != self._last_widget_size:
                # Размер виджета изменился - пересчитываем масштаб
                self._recompute_fsm_layout(place_radius, trans_width, trans_height)
                self._last_widget_size = current_size

        return place_radius, trans_width, trans_height
    
    def _calculate_dynamic_sizes(self):
        """Вычисляет динамические размеры элементов на основе доступного пространства."""
        width = self.width()
        height = self.height()
        
        # Минимальные отступы (адаптивные)
        margin_x = max(40, width * 0.05)
        margin_y = max(30, height * 0.05)
        
        # Вычисляем доступное пространство
        available_width = width - 2 * margin_x
        available_height = height - 2 * margin_y
        
        if available_width <= 0 or available_height <= 0:
            return self.base_place_radius, self.base_trans_width, self.base_trans_height
        
        # Адаптивное масштабирование в зависимости от режима раскладки
        if self.layout_mode == "fsm":
            # Для FSM используем более агрессивное масштабирование
            # Учитываем общее количество элементов
            total_elements = self.model.P + self.model.T
            avg_element_size = (self.base_place_radius * 2 + self.base_trans_width) / 2
            
            # Вычисляем оптимальный размер на основе доступного пространства
            # Используем диагональ для более точного расчета
            diagonal = math.sqrt(available_width ** 2 + available_height ** 2)
            element_density = total_elements / (available_width * available_height) if (available_width * available_height) > 0 else 0.001
            
            # Масштаб на основе плотности элементов
            if element_density > 0:
                optimal_size = math.sqrt((available_width * available_height) / (total_elements * 1.5))
                scale = optimal_size / avg_element_size
            else:
                scale = 1.0
            
            # Ограничиваем масштаб разумными пределами
            scale = max(0.4, min(scale, 1.5))
            
        elif self.layout_mode == "hier_demo":
            # Для иерархической раскладки учитываем вертикальное пространство
            vertical_space_needed = self.base_place_radius * 2 + self.base_trans_height + 100
            scale_y = available_height / vertical_space_needed if vertical_space_needed > 0 else 1.0
            
            horizontal_space_needed = max(self.model.P, self.model.T) * (self.base_place_radius * 2 + 40)
            scale_x = available_width / horizontal_space_needed if horizontal_space_needed > 0 else 1.0
            
            scale = max(0.4, min(scale_x, scale_y, 1.2))
            
        else:  # rows
            # Для рядов учитываем горизонтальное и вертикальное пространство
            if self.model.P > 1:
                space_per_place = available_width / self.model.P
                scale_x_places = min(1.2, space_per_place / (self.base_place_radius * 2.5))
            else:
                scale_x_places = 1.0
            
            if self.model.T > 1:
                space_per_trans = available_width / self.model.T
                scale_x_trans = min(1.2, space_per_trans / (self.base_trans_width * 2.5))
            else:
                scale_x_trans = 1.0
            
            scale_x = min(scale_x_places, scale_x_trans)
            
            vertical_space_needed = self.base_place_radius * 2 + self.base_trans_height + 80
            scale_y = min(1.2, available_height / vertical_space_needed) if vertical_space_needed > 0 else 1.0
            
            scale = max(0.4, min(scale_x, scale_y))
        
        place_radius = self.base_place_radius * scale
        trans_width = self.base_trans_width * scale
        trans_height = self.base_trans_height * scale
        
        return place_radius, trans_width, trans_height
    

    def _compute_layout_rows(self, place_radius, trans_width, trans_height):
        """Базовая раскладка в два ряда (как было изначально)."""
        width = self.width()
        height = self.height()

        margin_x = 60
        margin_y = 40

        # Места — верхний ряд
        if self.model.P > 1:
            step_places = (width - 2 * margin_x) / (self.model.P - 1)
        else:
            step_places = 0

        y_places = margin_y + place_radius
        for i in range(self.model.P):
            x = margin_x + i * step_places
            self.place_positions.append(QPointF(x, y_places))

        # Переходы — нижний ряд
        if self.model.T > 1:
            step_trans = (width - 2 * margin_x) / (self.model.T - 1)
        else:
            step_trans = 0

        y_trans = height - margin_y - trans_height / 2
        for j in range(self.model.T):
            x = margin_x + j * step_trans
            self.transition_positions.append(QPointF(x, y_trans))

    def _compute_layout_hier_demo(self, place_radius, trans_width, trans_height):
        """
        Условно иерархическая раскладка для демо (7 мест, 5 переходов),
        визуально приближенная к картинке из задания.
        """
        width = self.width()
        height = self.height()

        margin_x = 60
        margin_y = 40

        levels = 5  # число промежутков (даёт 6 уровней)
        gap_y = (height - 2 * margin_y) / max(1, levels)
        y_levels = [margin_y + gap_y * i for i in range(6)]

        # Шаблон координат в долях ширины
        def px(fraction: float) -> float:
            return margin_x + (width - 2 * margin_x) * fraction

        # Места
        coords_places = [
            (px(0.32), y_levels[0]),  # p1
            (px(0.68), y_levels[0]),  # p2
            (px(0.38), y_levels[2]),  # p3
            (px(0.62), y_levels[2]),  # p4
            (px(0.20), y_levels[4]),  # p5
            (px(0.40), y_levels[4]),  # p6
            (px(0.68), y_levels[4]),  # p7
        ]

        for idx in range(self.model.P):
            if idx < len(coords_places):
                x, y = coords_places[idx]
                self.place_positions.append(QPointF(x, y + place_radius))
            else:
                # если мест больше — добавляем внизу с шагом
                extra_y = y_levels[-1] + (idx - len(coords_places) + 1) * gap_y * 0.6
                self.place_positions.append(QPointF(px(0.5), extra_y))

        # Переходы
        coords_trans = [
            (px(0.50), y_levels[1]),  # t1
            (px(0.22), y_levels[3]),  # t2
            (px(0.42), y_levels[3]),  # t3
            (px(0.62), y_levels[3]),  # t4
            (px(0.70), y_levels[5]),  # t5
        ]

        for idx in range(self.model.T):
            if idx < len(coords_trans):
                x, y = coords_trans[idx]
                self.transition_positions.append(QPointF(x, y + trans_height / 2))
            else:
                extra_y = y_levels[-1] + (idx - len(coords_trans) + 1) * gap_y * 0.6
                self.transition_positions.append(QPointF(px(0.5), extra_y))

    def _recompute_fsm_layout(self, place_radius, trans_width, trans_height):
        """Пересчитывает раскладку FSM с сохранением относительных позиций при изменении размера."""
        if not self.place_positions or not self.transition_positions:
            self._compute_layout_fsm(place_radius, trans_width, trans_height)
            return
        
        width = self.width()
        height = self.height()
        widget_center_x = width / 2
        widget_center_y = height / 2
        
        # Находим текущие границы графа
        if self.place_positions:
            min_x = min(pos.x() for pos in self.place_positions)
            max_x = max(pos.x() for pos in self.place_positions)
            min_y = min(pos.y() for pos in self.place_positions)
            max_y = max(pos.y() for pos in self.place_positions)
            
            graph_width = max_x - min_x if max_x != min_x else 1
            graph_height = max_y - min_y if max_y != min_y else 1
            
            # Масштабируем и центрируем
            margin_x = 60
            margin_y = 40
            available_width = width - 2 * margin_x
            available_height = height - 2 * margin_y
            
            if graph_width > 0 and graph_height > 0:
                scale_x = available_width / graph_width
                scale_y = available_height / graph_height
                scale = min(scale_x, scale_y) * 0.9
                scale = max(0.3, min(scale, 1.5))
                
                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2
                
                # Масштабируем и центрируем места
                for i in range(len(self.place_positions)):
                    pos = self.place_positions[i]
                    new_x = (pos.x() - center_x) * scale + widget_center_x
                    new_y = (pos.y() - center_y) * scale + widget_center_y
                    self.place_positions[i] = QPointF(new_x, new_y)
                
                # Масштабируем и центрируем переходы
                for i in range(len(self.transition_positions)):
                    pos = self.transition_positions[i]
                    new_x = (pos.x() - center_x) * scale + widget_center_x
                    new_y = (pos.y() - center_y) * scale + widget_center_y
                    self.transition_positions[i] = QPointF(new_x, new_y)
                
                # Исправляем перекрытия после масштабирования
                self._fix_place_overlaps(place_radius)
                self._fix_all_overlaps(place_radius, trans_width, trans_height)

    def _compute_layout_fsm(self, place_radius, trans_width, trans_height):
        """
        Раскладка сети Петри как конечного автомата (иерархически по состояниям).
        Места представляют состояния, переходы - переходы между состояниями.
        """
        width = self.width()
        height = self.height()
        
        margin_x = 60
        margin_y = 40
        
        # Анализируем структуру сети для определения уровней иерархии
        # Строим граф связей: какие места связаны через переходы
        place_levels = self._compute_place_levels()
        
        # Вычисляем позиции по уровням
        available_width = width - 2 * margin_x
        available_height = height - 2 * margin_y
        
        # Распределяем места по уровням
        # Также определяем уровни переходов (между уровнями мест)
        level_groups = {}
        transition_levels = {}  # Уровни переходов
        
        for place_idx, level in place_levels.items():
            if level not in level_groups:
                level_groups[level] = []
            level_groups[level].append(place_idx)
        
        # Определяем уровни переходов на основе их входных и выходных мест
        # Переход должен быть размещен между уровнем входных мест и уровнем выходных мест
        for t_idx in range(self.model.T):
            input_places = [p for p in range(self.model.P) if self.model.W_in[t_idx][p] == 1]
            output_places = [p for p in range(self.model.P) if self.model.W_out[t_idx][p] == 1]
            
            if input_places and output_places:
                # Вычисляем средний уровень входных мест
                input_level = sum(place_levels.get(p, 0) for p in input_places) / len(input_places)
                # Вычисляем средний уровень выходных мест
                output_level = sum(place_levels.get(p, 0) for p in output_places) / len(output_places)
                
                # Переход размещается между входными и выходными местами
                # Используем уровень входных мест + 0.5, чтобы переход был между уровнями
                transition_levels[t_idx] = input_level + 0.5
            elif input_places:
                # Если есть только входные места, размещаем переход сразу после них
                input_level = sum(place_levels.get(p, 0) for p in input_places) / len(input_places)
                transition_levels[t_idx] = input_level + 0.5
            elif output_places:
                # Если есть только выходные места, размещаем переход перед ними
                output_level = sum(place_levels.get(p, 0) for p in output_places) / len(output_places)
                transition_levels[t_idx] = max(0, output_level - 0.5)
            else:
                # Если нет ни входных, ни выходных мест, размещаем на уровне 0
                transition_levels[t_idx] = 0
        
        # Определяем количество уровней (включая уровни переходов)
        max_place_level = max(place_levels.values()) if place_levels else 0
        # Уровни переходов могут быть дробными, используем максимальный уровень мест + 1 для переходов
        num_levels = int(max_place_level) + 2 if max_place_level >= 0 else 1
        
        # Минимальные расстояния между элементами (в пикселях, затем нормализуем)
        # Увеличиваем минимальные расстояния для предотвращения перекрытий
        min_place_distance = (place_radius * 2 + 50)  # Минимум 50 пикселей между центрами мест
        min_level_distance = (place_radius * 2 + trans_width + 80)  # Расстояние между уровнями (увеличено)
        
        # Вычисляем относительные позиции (нормализованные от 0 до 1)
        # Сначала размещаем в относительных координатах
        relative_place_positions = []
        
        # Вычисляем необходимую ширину и высоту графа в пикселях
        max_places_in_level = max(len(level_groups.get(level, [])) for level in range(num_levels)) if level_groups else 1
        required_height = max(1, max_places_in_level - 1) * min_place_distance
        required_width = max(1, num_levels - 1) * min_level_distance
        
        # Нормализуем минимальные расстояния относительно требуемого размера графа
        # Используем больший размер для нормализации
        normalization_size = max(required_width, required_height, available_width, available_height)
        
        if normalization_size > 0:
            norm_min_place_dist = min_place_distance / normalization_size
            norm_min_level_dist = min_level_distance / normalization_size
        else:
            norm_min_place_dist = 0.1
            norm_min_level_dist = 0.2
        
        # Размещаем места по уровням с учетом минимальных расстояний
        # Увеличиваем минимальные расстояния для лучшего предотвращения перекрытий
        norm_min_place_dist = max(norm_min_place_dist, 0.2)  # Минимум 20% от высоты (увеличено)
        norm_min_level_dist = max(norm_min_level_dist, 0.25)  # Минимум 25% от ширины (увеличено)
        
        for level in range(num_levels):
            places_in_level = level_groups.get(level, [])
            if not places_in_level:
                continue
            
            # Относительная позиция X уровня
            rel_x_level = level * norm_min_level_dist
            
            # Вертикальное распределение мест в уровне с учетом минимальных расстояний
            num_places_in_level = len(places_in_level)
            if num_places_in_level > 1:
                # Вычисляем общую высоту, необходимую для размещения всех мест
                total_height_needed = (num_places_in_level - 1) * norm_min_place_dist
                # Начинаем с отступа сверху
                start_y = (1.0 - total_height_needed) / 2
                place_step_y = norm_min_place_dist
            else:
                start_y = 0.5
                place_step_y = 0
            
            for idx, place_idx in enumerate(places_in_level):
                rel_y_pos = start_y + idx * place_step_y
                relative_place_positions.append((place_idx, rel_x_level, rel_y_pos))
        
        # Находим границы относительных координат для центрирования
        if relative_place_positions:
            min_rel_x = min(rel_x for _, rel_x, _ in relative_place_positions)
            max_rel_x = max(rel_x for _, rel_x, _ in relative_place_positions)
            min_rel_y = min(rel_y for _, _, rel_y in relative_place_positions)
            max_rel_y = max(rel_y for _, _, rel_y in relative_place_positions)
            
            graph_rel_width = max_rel_x - min_rel_x if max_rel_x != min_rel_x else 1.0
            graph_rel_height = max_rel_y - min_rel_y if max_rel_y != min_rel_y else 1.0
        else:
            graph_rel_width = 1.0
            graph_rel_height = 1.0
            min_rel_x = 0
            min_rel_y = 0
        
        # Масштабируем и центрируем относительно доступного пространства
        # Используем требуемые размеры графа в пикселях для правильного масштабирования
        if graph_rel_width > 0 and graph_rel_height > 0:
            # Вычисляем требуемый размер графа в пикселях на основе минимальных расстояний
            # Используем фактические требуемые размеры для более точного масштабирования
            if required_width > 0 and required_height > 0:
                # Используем фактические требуемые размеры
                required_pixel_width = required_width
                required_pixel_height = required_height
            elif normalization_size > 0:
                # Fallback: преобразуем относительные размеры в пиксели
                required_pixel_width = graph_rel_width * normalization_size
                required_pixel_height = graph_rel_height * normalization_size
            else:
                # Fallback: используем доступное пространство
                required_pixel_width = max(required_width, available_width * 0.7)
                required_pixel_height = max(required_height, available_height * 0.7)
            
            # Вычисляем масштаб с учетом отступов
            # Используем более консервативный подход - масштабируем так, чтобы точно поместилось
            scale_x = available_width / required_pixel_width if required_pixel_width > 0 else 1.0
            scale_y = available_height / required_pixel_height if required_pixel_height > 0 else 1.0
            scale = min(scale_x, scale_y) * 0.8  # Более консервативный отступ (0.8) для гарантии
            
            # НЕ ограничиваем масштаб сохраненным значением при первой инициализации
            # Это позволяет графу правильно масштабироваться при первом отображении
            # Ограничиваем только при изменении размера (в _recompute_fsm_layout)
            
            # Ограничиваем масштаб разумными пределами
            scale = max(0.05, min(scale, 3.0))  # Минимум 0.05, максимум 3.0 для очень больших графов
            
            # Сохраняем масштаб только если он был рассчитан правильно
            # При первой инициализации или смене модели _last_scale будет None, поэтому не ограничиваем
            if self._last_scale is None:
                # Первая инициализация - сохраняем рассчитанный масштаб
                self._last_scale = scale
            # При последующих вызовах _last_scale будет использоваться только в _recompute_fsm_layout
        else:
            scale = 1.0
        
        # Центр графа в относительных координатах
        center_rel_x = (min_rel_x + max_rel_x) / 2
        center_rel_y = (min_rel_y + max_rel_y) / 2
        
        # Центр виджета
        widget_center_x = width / 2
        widget_center_y = height / 2
        
        # Преобразуем относительные координаты в абсолютные с центрированием
        self.place_positions = [QPointF(0, 0)] * self.model.P
        for place_idx, rel_x, rel_y in relative_place_positions:
            # Нормализуем относительно центра графа
            norm_x = (rel_x - center_rel_x) * scale + widget_center_x
            norm_y = (rel_y - center_rel_y) * scale + widget_center_y
            self.place_positions[place_idx] = QPointF(norm_x, norm_y)
        
        # Проверяем и исправляем перекрытия мест
        self._fix_place_overlaps(place_radius)
        
        # Размещаем переходы между соответствующими местами
        # В FSM входные места слева, выходные справа
        self.transition_positions = []
        
        for t_idx in range(self.model.T):
            # Находим входные и выходные места для этого перехода
            input_places = [p for p in range(self.model.P) if self.model.W_in[t_idx][p] == 1]
            output_places = [p for p in range(self.model.P) if self.model.W_out[t_idx][p] == 1]
            
            if not input_places or not output_places:
                # Если нет входов или выходов, размещаем переход в центре
                self.transition_positions.append(QPointF(widget_center_x, widget_center_y))
                continue
            
            # Вычисляем среднюю позицию входных и выходных мест
            input_x = sum(self.place_positions[p].x() for p in input_places) / len(input_places)
            input_y = sum(self.place_positions[p].y() for p in input_places) / len(input_places)
            
            output_x = sum(self.place_positions[p].x() for p in output_places) / len(output_places)
            output_y = sum(self.place_positions[p].y() for p in output_places) / len(output_places)
            
            # Размещаем переход между входными (слева) и выходными (справа) местами
            # Используем уровень перехода для определения позиции
            trans_level = transition_levels.get(t_idx, 0)
            
            # Вычисляем X позицию на основе уровня перехода
            # В FSM переходы должны быть размещены между уровнями мест
            # Используем уровень перехода для определения позиции X
            max_place_level = max(place_levels.values()) if place_levels else 0
            
            if max_place_level > 0:
                # Нормализуем уровень перехода относительно уровней мест
                # Переходы размещаются между уровнями, поэтому используем дробные значения
                level_fraction = trans_level / (max_place_level + 1) if max_place_level > 0 else 0.5
            else:
                level_fraction = 0.5
            
            # Вычисляем X позицию на основе уровня
            trans_x = margin_x + level_fraction * available_width
            trans_x = max(margin_x + trans_width/2, min(trans_x, width - margin_x - trans_width/2))
            
            # Y позиция - средняя между входными и выходными местами
            # Но не выходим за границы виджета
            trans_y = (input_y + output_y) / 2
            trans_y = max(margin_y + trans_height/2, min(trans_y, height - margin_y - trans_height/2))
            
            # Минимальное расстояние от мест и других переходов
            min_distance_from_place = place_radius + max(trans_width, trans_height) / 2 + 40
            min_distance_from_trans = max(trans_width, trans_height) + 30
            
            # Итеративно исправляем перекрытия до тех пор, пока они не будут устранены
            max_iterations = 10
            for iteration in range(max_iterations):
                has_overlap = False
                
                # Проверяем расстояние до ВСЕХ мест (не только связанных)
                for p in range(self.model.P):
                    dx = trans_x - self.place_positions[p].x()
                    dy = trans_y - self.place_positions[p].y()
                    distance = math.sqrt(dx * dx + dy * dy)
                    
                    if distance < min_distance_from_place:
                        has_overlap = True
                        # Вычисляем направление смещения
                        if distance > 0:
                            # Смещаем от места
                            offset_x = (dx / distance) * (min_distance_from_place - distance + 5)
                            offset_y = (dy / distance) * (min_distance_from_place - distance + 5)
                        else:
                            # Если точно в центре, смещаем вправо
                            offset_x = min_distance_from_place
                            offset_y = 0
                        
                        trans_x += offset_x
                        trans_y += offset_y
                
                # Проверяем расстояние до уже размещенных переходов
                for existing_trans_pos in self.transition_positions:
                    dx = trans_x - existing_trans_pos.x()
                    dy = trans_y - existing_trans_pos.y()
                    distance = math.sqrt(dx * dx + dy * dy)
                    
                    if distance < min_distance_from_trans:
                        has_overlap = True
                        if distance > 0:
                            # Смещаем от другого перехода
                            offset_x = (dx / distance) * (min_distance_from_trans - distance + 5)
                            offset_y = (dy / distance) * (min_distance_from_trans - distance + 5)
                            trans_x += offset_x
                            trans_y += offset_y
                        else:
                            # Если точно в одной точке, смещаем диагонально
                            trans_x += min_distance_from_trans
                            trans_y += min_distance_from_trans
                
                if not has_overlap:
                    break
            
            self.transition_positions.append(QPointF(trans_x, trans_y))
        
        # Финальная проверка и исправление всех перекрытий
        self._fix_all_overlaps(place_radius, trans_width, trans_height)
        
        # КРИТИЧЕСКИ ВАЖНО: После размещения всех элементов ОБЯЗАТЕЛЬНО проверяем границы
        # и масштабируем так, чтобы ВСЕ элементы точно поместились в видимую область
        if self.place_positions and self.transition_positions:
            # Находим реальные границы всех элементов с учетом их размеров
            all_positions = list(self.place_positions) + list(self.transition_positions)
            
            # Для мест учитываем радиус
            place_min_x = min(pos.x() - place_radius for pos in self.place_positions) if self.place_positions else 0
            place_max_x = max(pos.x() + place_radius for pos in self.place_positions) if self.place_positions else 0
            place_min_y = min(pos.y() - place_radius for pos in self.place_positions) if self.place_positions else 0
            place_max_y = max(pos.y() + place_radius for pos in self.place_positions) if self.place_positions else 0
            
            # Для переходов учитываем размеры
            trans_min_x = min(pos.x() - trans_width/2 for pos in self.transition_positions) if self.transition_positions else 0
            trans_max_x = max(pos.x() + trans_width/2 for pos in self.transition_positions) if self.transition_positions else 0
            trans_min_y = min(pos.y() - trans_height/2 for pos in self.transition_positions) if self.transition_positions else 0
            trans_max_y = max(pos.y() + trans_height/2 for pos in self.transition_positions) if self.transition_positions else 0
            
            # Общие границы
            graph_min_x = min(place_min_x, trans_min_x) if (self.place_positions and self.transition_positions) else (place_min_x if self.place_positions else trans_min_x)
            graph_max_x = max(place_max_x, trans_max_x) if (self.place_positions and self.transition_positions) else (place_max_x if self.place_positions else trans_max_x)
            graph_min_y = min(place_min_y, trans_min_y) if (self.place_positions and self.transition_positions) else (place_min_y if self.place_positions else trans_min_y)
            graph_max_y = max(place_max_y, trans_max_y) if (self.place_positions and self.transition_positions) else (place_max_y if self.place_positions else trans_max_y)
            
            graph_width = graph_max_x - graph_min_x
            graph_height = graph_max_y - graph_min_y
            
            # Центр графа
            center_x = (graph_min_x + graph_max_x) / 2
            center_y = (graph_min_y + graph_max_y) / 2
            
            # Вычисляем масштаб так, чтобы граф точно поместился с отступами
            # Используем более консервативные отступы для гарантии
            safe_margin_x = margin_x * 1.2  # Увеличиваем отступы
            safe_margin_y = margin_y * 1.2
            safe_available_width = width - 2 * safe_margin_x
            safe_available_height = height - 2 * safe_margin_y
            
            if graph_width > 0 and graph_height > 0:
                scale_x = safe_available_width / graph_width if graph_width > 0 else 1.0
                scale_y = safe_available_height / graph_height if graph_height > 0 else 1.0
                final_scale = min(scale_x, scale_y) * 0.95  # 95% для гарантии
                
                # Ограничиваем масштаб разумными пределами
                final_scale = max(0.05, min(final_scale, 3.0))
                
                # ПРИМЕНЯЕМ масштаб ко всем элементам
                for i in range(len(self.place_positions)):
                    pos = self.place_positions[i]
                    new_x = (pos.x() - center_x) * final_scale + widget_center_x
                    new_y = (pos.y() - center_y) * final_scale + widget_center_y
                    self.place_positions[i] = QPointF(new_x, new_y)
                
                for i in range(len(self.transition_positions)):
                    pos = self.transition_positions[i]
                    new_x = (pos.x() - center_x) * final_scale + widget_center_x
                    new_y = (pos.y() - center_y) * final_scale + widget_center_y
                    self.transition_positions[i] = QPointF(new_x, new_y)
                
                # Обновляем сохраненный масштаб
                self._last_scale = final_scale
                
                # Упрощенная финальная проверка - просто убеждаемся, что масштаб правильный
                # Не делаем повторное масштабирование, чтобы избежать зависаний
    
    def _fix_place_overlaps(self, place_radius):
        """Исправляет перекрытия мест, смещая их при необходимости."""
        min_distance = place_radius * 2 + 40  # Минимальное расстояние между центрами (увеличено)
        
        # Итеративный алгоритм для устранения всех перекрытий
        max_iterations = 20
        for iteration in range(max_iterations):
            has_overlap = False
            
            # Проверяем все пары мест
            for i in range(len(self.place_positions)):
                for j in range(i + 1, len(self.place_positions)):
                    pos_i = self.place_positions[i]
                    pos_j = self.place_positions[j]
                    
                    dx = pos_j.x() - pos_i.x()
                    dy = pos_j.y() - pos_i.y()
                    distance = math.sqrt(dx * dx + dy * dy)
                    
                    if distance < min_distance:
                        has_overlap = True
                        if distance > 0:
                            # Вычисляем необходимое смещение
                            overlap = min_distance - distance + 5  # Увеличен отступ
                            # Смещаем оба места в противоположные стороны
                            offset_x = (dx / distance) * overlap / 2
                            offset_y = (dy / distance) * overlap / 2
                            
                            # Обновляем позиции
                            self.place_positions[i] = QPointF(pos_i.x() - offset_x, pos_i.y() - offset_y)
                            self.place_positions[j] = QPointF(pos_j.x() + offset_x, pos_j.y() + offset_y)
                        else:
                            # Если места в одной точке, разводим их
                            self.place_positions[j] = QPointF(pos_j.x() + min_distance, pos_j.y())
            
            if not has_overlap:
                break
    
    def _fix_all_overlaps(self, place_radius, trans_width, trans_height):
        """Исправляет все перекрытия между местами и переходами."""
        min_place_distance = place_radius * 2 + 40  # Увеличено
        min_trans_place_distance = place_radius + max(trans_width, trans_height) / 2 + 50  # Увеличено
        min_trans_distance = max(trans_width, trans_height) + 40  # Увеличено
        
        # Итеративный алгоритм для устранения всех перекрытий
        max_iterations = 20
        for iteration in range(max_iterations):
            has_overlap = False
            
            # Проверяем перекрытия мест с местами
            for i in range(len(self.place_positions)):
                for j in range(i + 1, len(self.place_positions)):
                    pos_i = self.place_positions[i]
                    pos_j = self.place_positions[j]
                    
                    dx = pos_j.x() - pos_i.x()
                    dy = pos_j.y() - pos_i.y()
                    distance = math.sqrt(dx * dx + dy * dy)
                    
                    if distance < min_place_distance:
                        has_overlap = True
                        if distance > 0:
                            overlap = min_place_distance - distance + 2
                            offset_x = (dx / distance) * overlap / 2
                            offset_y = (dy / distance) * overlap / 2
                            self.place_positions[i] = QPointF(pos_i.x() - offset_x, pos_i.y() - offset_y)
                            self.place_positions[j] = QPointF(pos_j.x() + offset_x, pos_j.y() + offset_y)
                        else:
                            self.place_positions[j] = QPointF(pos_j.x() + min_place_distance, pos_j.y())
            
            # Проверяем перекрытия переходов с местами
            for t_idx, trans_pos in enumerate(self.transition_positions):
                for p_idx, place_pos in enumerate(self.place_positions):
                    dx = trans_pos.x() - place_pos.x()
                    dy = trans_pos.y() - place_pos.y()
                    distance = math.sqrt(dx * dx + dy * dy)
                    
                    if distance < min_trans_place_distance:
                        has_overlap = True
                        if distance > 0:
                            overlap = min_trans_place_distance - distance + 5
                            offset_x = (dx / distance) * overlap
                            offset_y = (dy / distance) * overlap
                            # Смещаем только переход
                            self.transition_positions[t_idx] = QPointF(
                                trans_pos.x() + offset_x,
                                trans_pos.y() + offset_y
                            )
                        else:
                            self.transition_positions[t_idx] = QPointF(
                                place_pos.x() + min_trans_place_distance,
                                place_pos.y()
                            )
            
            # Проверяем перекрытия переходов с переходами
            for i in range(len(self.transition_positions)):
                for j in range(i + 1, len(self.transition_positions)):
                    pos_i = self.transition_positions[i]
                    pos_j = self.transition_positions[j]
                    
                    dx = pos_j.x() - pos_i.x()
                    dy = pos_j.y() - pos_i.y()
                    distance = math.sqrt(dx * dx + dy * dy)
                    
                    if distance < min_trans_distance:
                        has_overlap = True
                        if distance > 0:
                            overlap = min_trans_distance - distance + 5
                            offset_x = (dx / distance) * overlap / 2
                            offset_y = (dy / distance) * overlap / 2
                            self.transition_positions[i] = QPointF(pos_i.x() - offset_x, pos_i.y() - offset_y)
                            self.transition_positions[j] = QPointF(pos_j.x() + offset_x, pos_j.y() + offset_y)
                        else:
                            self.transition_positions[j] = QPointF(pos_j.x() + min_trans_distance, pos_j.y())
            
            if not has_overlap:
                break
    
    def _compute_place_levels(self):
        """
        Вычисляет уровни иерархии для мест на основе структуры сети.
        В FSM входные места размещаются слева (меньший уровень), выходные справа (больший уровень).
        Использует топологическую сортировку для правильного определения иерархии.
        Возвращает словарь {place_index: level}, где level - уровень иерархии (0 - начальный).
        """
        # Инициализируем уровни
        levels = {}
        
        # Находим начальные места (места без входящих дуг от переходов)
        # Место является начальным, если нет переходов, которые в него ведут
        initial_places = []
        for p in range(self.model.P):
            has_input = False
            for t in range(self.model.T):
                if self.model.W_out[t][p] == 1:
                    has_input = True
                    break
            if not has_input:
                initial_places.append(p)
                levels[p] = 0
        
        # Если нет явных начальных мест, используем все места как начальные
        if not initial_places:
            for p in range(self.model.P):
                initial_places.append(p)
                levels[p] = 0
        
        # Используем BFS для распространения уровней, но с правильной логикой:
        # Место -> Переход -> Место (каждый переход увеличивает уровень на 1)
        visited = set(initial_places)
        queue = list(initial_places)
        
        # Защита от бесконечного цикла: ограничиваем количество итераций
        max_iterations = self.model.P * self.model.T * 2  # Максимум итераций
        iteration_count = 0
        
        # Обрабатываем очередь до тех пор, пока не обработаем все достижимые места
        while queue and iteration_count < max_iterations:
            iteration_count += 1
            current_place = queue.pop(0)
            current_level = levels.get(current_place, 0)
            
            # Находим переходы, которые входят в текущее место (W_in)
            for t_idx in range(self.model.T):
                if self.model.W_in[t_idx][current_place] == 1:
                    # Этот переход активируется из текущего места
                    # Уровень перехода = уровень входного места + 0.5 (между уровнями)
                    # Но для размещения мест нам нужны целые уровни
                    
                    # Выходные места этого перехода получают уровень = текущий уровень + 1
                    for out_place in range(self.model.P):
                        if self.model.W_out[t_idx][out_place] == 1:
                            new_level = current_level + 1
                            
                            # Если место еще не посещено, устанавливаем уровень
                            if out_place not in visited:
                                levels[out_place] = new_level
                                visited.add(out_place)
                                queue.append(out_place)
                            else:
                                # Если место уже посещено, используем максимальный уровень
                                # (для обработки циклов и множественных путей)
                                # НО: не добавляем в очередь снова, чтобы избежать бесконечного цикла
                                if out_place in levels:
                                    # Для циклов: если место уже имеет уровень, обновляем только если новый больше
                                    if new_level > levels[out_place]:
                                        levels[out_place] = new_level
                                        # НЕ добавляем в очередь снова, чтобы избежать бесконечного цикла
        
        # Убеждаемся, что все места имеют уровень
        for p in range(self.model.P):
            if p not in levels:
                # Если место не было достигнуто (изолированное или только с входящими дугами),
                # размещаем его на максимальном уровне + 1
                max_level = max(levels.values()) if levels else 0
                levels[p] = max_level + 1
        
        # Нормализуем уровни: начинаем с 0 и идем последовательно
        if levels:
            min_level = min(levels.values())
            # Сдвигаем все уровни так, чтобы минимальный был 0
            for p in levels:
                levels[p] = levels[p] - min_level
        
        return levels
    
    # --- Новые алгоритмы размещения (NetworkX/Graphviz) ---
    
    def _model_to_networkx_graph(self):
        """Преобразует модель сети Петри в NetworkX DiGraph для использования в алгоритмах размещения."""
        if not HAS_NETWORKX:
            return None
        
        G = nx.DiGraph()
        
        # Добавляем узлы: места и переходы
        for p in range(self.model.P):
            G.add_node(f"place_{p}", node_type="place", index=p)
        for t in range(self.model.T):
            G.add_node(f"trans_{t}", node_type="transition", index=t)
        
        # Добавляем дуги: из мест в переходы (W_in) и из переходов в места (W_out)
        for t_idx in range(self.model.T):
            for p_idx in range(self.model.P):
                if self.model.W_in[t_idx][p_idx] == 1:
                    G.add_edge(f"place_{p_idx}", f"trans_{t_idx}")
                if self.model.W_out[t_idx][p_idx] == 1:
                    G.add_edge(f"trans_{t_idx}", f"place_{p_idx}")
        
        return G
    
    def _normalize_positions(self, pos_dict, place_radius, trans_width, trans_height):
        """Нормализует позиции из NetworkX/Graphviz под размер виджета с центрированием."""
        if not pos_dict:
            return
        
        width = self.width()
        height = self.height()
        margin_x = 60
        margin_y = 40
        available_width = width - 2 * margin_x
        available_height = height - 2 * margin_y
        
        # Находим границы графа
        all_x = [pos[0] for pos in pos_dict.values()]
        all_y = [pos[1] for pos in pos_dict.values()]
        
        if not all_x or not all_y:
            return
        
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        graph_width = max_x - min_x if max_x != min_x else 1
        graph_height = max_y - min_y if max_y != min_y else 1
        
        # Масштабируем и центрируем
        scale_x = available_width / graph_width if graph_width > 0 else 1.0
        scale_y = available_height / graph_height if graph_height > 0 else 1.0
        scale = min(scale_x, scale_y) * 0.9
        
        # Сохраняем масштаб для предотвращения увеличения
        if hasattr(self, '_last_scale') and self._last_scale is not None:
            scale = min(scale, self._last_scale)
        scale = max(0.3, min(scale, 1.5))
        self._last_scale = scale
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        widget_center_x = width / 2
        widget_center_y = height / 2
        
        # Преобразуем позиции
        self.place_positions = [QPointF(0, 0)] * self.model.P
        self.transition_positions = []
        
        for node_id, (x, y) in pos_dict.items():
            # Масштабируем и центрируем
            norm_x = (x - center_x) * scale + widget_center_x
            norm_y = (y - center_y) * scale + widget_center_y
            
            if node_id.startswith("place_"):
                p_idx = int(node_id.split("_")[1])
                if 0 <= p_idx < self.model.P:
                    self.place_positions[p_idx] = QPointF(norm_x, norm_y)
            elif node_id.startswith("trans_"):
                t_idx = int(node_id.split("_")[1])
                if 0 <= t_idx < self.model.T:
                    # Убеждаемся, что список достаточно длинный
                    while len(self.transition_positions) <= t_idx:
                        self.transition_positions.append(QPointF(0, 0))
                    self.transition_positions[t_idx] = QPointF(norm_x, norm_y)
        
        # Заполняем недостающие переходы
        while len(self.transition_positions) < self.model.T:
            self.transition_positions.append(QPointF(widget_center_x, widget_center_y))
    
    def _compute_layout_hierarchical(self, place_radius, trans_width, trans_height):
        """
        Стратегия 1: Иерархический поток (Hierarchical / Sugiyama)
        Использует Graphviz dot с rankdir='LR' для размещения слева направо.
        """
        if not HAS_NETWORKX:
            # Fallback на простую раскладку
            self._compute_layout_rows(place_radius, trans_width, trans_height)
            return
        
        G = self._model_to_networkx_graph()
        if G is None:
            self._compute_layout_rows(place_radius, trans_width, trans_height)
            return
        
        try:
            # Пробуем использовать Graphviz через pydot
            if HAS_PYDOT:
                # Устанавливаем параметры графа для иерархического размещения
                if 'graph' not in G.graph:
                    G.graph['graph'] = {}
                G.graph['graph']['rankdir'] = 'LR'
                G.graph['graph']['nodesep'] = '0.5'
                G.graph['graph']['ranksep'] = '1.0'
                pos = nx.nx_pydot.graphviz_layout(G, prog='dot')
            else:
                # Fallback: используем встроенный алгоритм NetworkX
                pos = nx.spring_layout(G, k=2.0, iterations=50)
        except Exception as e:
            # Если Graphviz недоступен, используем fallback
            pos = nx.spring_layout(G, k=2.0, iterations=50)
        
        # Пост-обработка: Grid Snap для Y координат (округление до уровней)
        if pos:
            # Группируем узлы по Y координатам и округляем до ближайшего уровня
            y_values = sorted(set(y for x, y in pos.values()))
            y_levels = {y: i for i, y in enumerate(y_values)}
            
            for node_id in pos:
                x, y = pos[node_id]
                # Находим ближайший уровень
                closest_y = min(y_values, key=lambda y_val: abs(y_val - y))
                pos[node_id] = (x, closest_y)
        
        self._normalize_positions(pos, place_radius, trans_width, trans_height)
        # Исправляем перекрытия
        self._fix_place_overlaps(place_radius)
        self._fix_all_overlaps(place_radius, trans_width, trans_height)
    
    def _compute_layout_orthogonal(self, place_radius, trans_width, trans_height):
        """
        Стратегия 2: Инженерная схема (Orthogonal Circuit)
        Использует Graphviz dot с splines='ortho' для прямоугольных линий.
        """
        if not HAS_NETWORKX:
            self._compute_layout_rows(place_radius, trans_width, trans_height)
            return
        
        G = self._model_to_networkx_graph()
        if G is None:
            self._compute_layout_rows(place_radius, trans_width, trans_height)
            return
        
        try:
            if HAS_PYDOT:
                # Устанавливаем параметры для ортогонального размещения
                if 'graph' not in G.graph:
                    G.graph['graph'] = {}
                G.graph['graph']['rankdir'] = 'LR'
                G.graph['graph']['splines'] = 'ortho'
                G.graph['graph']['ordering'] = 'out'
                pos = nx.nx_pydot.graphviz_layout(G, prog='dot')
            else:
                # Fallback: используем spring layout
                pos = nx.spring_layout(G, k=2.0, iterations=50)
        except Exception as e:
            pos = nx.spring_layout(G, k=2.0, iterations=50)
        
        self._normalize_positions(pos, place_radius, trans_width, trans_height)
        # Исправляем перекрытия
        self._fix_place_overlaps(place_radius)
        self._fix_all_overlaps(place_radius, trans_width, trans_height)
    
    def _compute_layout_organic(self, place_radius, trans_width, trans_height):
        """
        Стратегия 3: Симметричный/Органический (Symmetric / Force-Directed)
        Использует Kamada-Kawai или Graphviz neato для симметричного размещения.
        """
        if not HAS_NETWORKX:
            self._compute_layout_rows(place_radius, trans_width, trans_height)
            return
        
        G = self._model_to_networkx_graph()
        if G is None:
            self._compute_layout_rows(place_radius, trans_width, trans_height)
            return
        
        try:
            # Пробуем Kamada-Kawai (встроенный в NetworkX)
            if len(G.nodes()) >= 3:
                try:
                    pos = nx.kamada_kawai_layout(G)
                except:
                    # Если Kamada-Kawai не работает, используем spring
                    pos = nx.spring_layout(G, k=2.5, iterations=100)
            else:
                pos = nx.spring_layout(G, k=2.5, iterations=100)
            
            # Альтернатива: через Graphviz neato (если доступен)
            if HAS_PYDOT:
                try:
                    pos_neato = nx.nx_pydot.graphviz_layout(G, prog='neato')
                    if pos_neato:
                        pos = pos_neato
                except:
                    pass  # Используем уже вычисленный pos
        except Exception as e:
            # Fallback на spring layout
            pos = nx.spring_layout(G, k=2.5, iterations=100)
        
        # Пост-обработка: масштабирование для "дыхания" сети
        if pos:
            # Увеличиваем масштаб для лучшей визуализации
            scale_factor = 2.5
            for node_id in pos:
                x, y = pos[node_id]
                pos[node_id] = (x * scale_factor, y * scale_factor)
        
        self._normalize_positions(pos, place_radius, trans_width, trans_height)
        # Исправляем перекрытия
        self._fix_place_overlaps(place_radius)
        self._fix_all_overlaps(place_radius, trans_width, trans_height)

    # --- Рисование ---

    def paintEvent(self, event):
        if self.model is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Вычисляем размеры элементов (без пересчета позиций при перетаскивании)
        place_radius, trans_w, trans_h = self._compute_layout()

        # Цвета
        bg = self.palette().window().color()
        painter.fillRect(self.rect(), bg)

        pen_default = QPen(self.palette().windowText().color(), 2)
        painter.setPen(pen_default)

        # 1. Рисуем дуги (сначала, чтобы были под объектами)
        self._draw_arcs(painter, place_radius, trans_w, trans_h)

        # 2. Рисуем места
        self._draw_places(painter, place_radius)

        # 3. Рисуем переходы
        self._draw_transitions(painter, trans_w, trans_h)

    def _draw_places(self, painter, radius):
        pen = QPen(Qt.black, 2)
        painter.setPen(pen)
        for i, center in enumerate(self.place_positions):
            # Обводка места
            painter.setBrush(QBrush(Qt.white))
            painter.drawEllipse(center, radius, radius)

            # Подпись места p_i
            label = f"p{i + 1}"
            painter.drawText(
                center.x() - radius,
                center.y() - radius - 4,
                2 * radius,
                16,
                Qt.AlignCenter,
                label,
            )

            # Фишки (Marking)
            tokens = 0
            if 0 <= i < len(self.model.M):
                tokens = self.model.M[i]
            tokens = max(0, min(self.model.MAX_TOKENS, tokens))
            self._draw_tokens_in_place(painter, center, radius, tokens)

    def _draw_tokens_in_place(self, painter, center, radius, tokens):
        """Рисует от 0 до 3 фишек внутри круга."""
        if tokens <= 0:
            return

        token_radius = radius / 4
        painter.setBrush(QBrush(Qt.black))

        # Предопределённые позиции относительно центра
        offsets = {
            1: [QPointF(0, 0)],
            2: [QPointF(-token_radius, 0), QPointF(token_radius, 0)],
            3: [
                QPointF(-token_radius, -token_radius / 2),
                QPointF(token_radius, -token_radius / 2),
                QPointF(0, token_radius),
            ],
        }

        for off in offsets.get(tokens, []):
            c = QPointF(center.x() + off.x(), center.y() + off.y())
            painter.drawEllipse(c, token_radius, token_radius)

    def _draw_transitions(self, painter, w, h):
        pen = QPen(Qt.darkGray, 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(180, 220, 255)))
        for j, center in enumerate(self.transition_positions):
            x = center.x() - w / 2
            y = center.y() - h / 2
            painter.drawRect(x, y, w, h)

            # Подпись перехода t_j
            label = f"t{j + 1}"
            painter.drawText(
                x,
                y + h + 4,
                w,
                16,
                Qt.AlignCenter,
                label,
            )

    def _draw_arcs(self, painter, place_radius, trans_w, trans_h):
        pen = QPen(Qt.darkGray, 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        # Для ортогонального режима используем ломаные линии
        if self.layout_mode == "orthogonal":
            # Входные дуги: из мест в переходы (W_in)
            for t_idx in range(self.model.T):
                for p_idx in range(self.model.P):
                    if self.model.W_in[t_idx][p_idx] == 1:
                        self._draw_orthogonal_arrow_place_to_transition(
                            painter, p_idx, t_idx, place_radius, trans_w, trans_h
                        )

            # Выходные дуги: из переходов в места (W_out)
            for t_idx in range(self.model.T):
                for p_idx in range(self.model.P):
                    if self.model.W_out[t_idx][p_idx] == 1:
                        self._draw_orthogonal_arrow_transition_to_place(
                            painter, t_idx, p_idx, place_radius, trans_w, trans_h
                        )
        else:
            # Обычные прямые линии для других режимов
            # Входные дуги: из мест в переходы (W_in)
            for t_idx in range(self.model.T):
                for p_idx in range(self.model.P):
                    if self.model.W_in[t_idx][p_idx] == 1:
                        self._draw_arrow_place_to_transition(
                            painter, p_idx, t_idx, place_radius, trans_w, trans_h
                        )

            # Выходные дуги: из переходов в места (W_out)
            for t_idx in range(self.model.T):
                for p_idx in range(self.model.P):
                    if self.model.W_out[t_idx][p_idx] == 1:
                        self._draw_arrow_transition_to_place(
                            painter, t_idx, p_idx, place_radius, trans_w, trans_h
                        )

    def _draw_arrow_place_to_transition(self, painter, p_idx, t_idx, r_place, w_trans, h_trans):
        if p_idx >= len(self.place_positions) or t_idx >= len(self.transition_positions):
            return

        start = self.place_positions[p_idx]
        end_center = self.transition_positions[t_idx]

        # Вычисляем угол направления стрелки
        dx = end_center.x() - start.x()
        dy = end_center.y() - start.y()
        angle = math.atan2(dy, dx)
        
        # Стартовая точка — на краю круга (не внутри)
        start_pt = QPointF(
            start.x() + r_place * math.cos(angle),
            start.y() + r_place * math.sin(angle)
        )
        
        # Конечная точка — на краю прямоугольника (не внутри)
        # Определяем ближайшую сторону прямоугольника
        trans_half_w = w_trans / 2
        trans_half_h = h_trans / 2
        
        # Вычисляем точку пересечения линии с прямоугольником
        # Используем простой алгоритм: находим ближайшую точку на границе прямоугольника
        if abs(dx) > abs(dy):
            # Горизонтальное направление преобладает
            if dx > 0:
                # Стрелка идет вправо - попадаем в правую сторону
                end_pt = QPointF(end_center.x() + trans_half_w, end_center.y())
            else:
                # Стрелка идет влево - попадаем в левую сторону
                end_pt = QPointF(end_center.x() - trans_half_w, end_center.y())
        else:
            # Вертикальное направление преобладает
            if dy > 0:
                # Стрелка идет вниз - попадаем в нижнюю сторону
                end_pt = QPointF(end_center.x(), end_center.y() + trans_half_h)
            else:
                # Стрелка идет вверх - попадаем в верхнюю сторону
                end_pt = QPointF(end_center.x(), end_center.y() - trans_half_h)
        
        # Корректируем точку конца с учетом угла для более точного попадания на границу
        # Вычисляем точку пересечения линии с прямоугольником
        end_pt = self._intersect_line_with_rect(
            start_pt, end_center, trans_half_w, trans_half_h
        )

        self._draw_arrow_line(painter, start_pt, end_pt)

    def _draw_arrow_transition_to_place(self, painter, t_idx, p_idx, r_place, w_trans, h_trans):
        if p_idx >= len(self.place_positions) or t_idx >= len(self.transition_positions):
            return

        start_center = self.transition_positions[t_idx]
        end = self.place_positions[p_idx]

        # Вычисляем угол направления стрелки
        dx = end.x() - start_center.x()
        dy = end.y() - start_center.y()
        angle = math.atan2(dy, dx)
        
        # Стартовая точка — на краю прямоугольника (не внутри)
        trans_half_w = w_trans / 2
        trans_half_h = h_trans / 2
        
        start_pt = self._intersect_line_with_rect(
            end, start_center, trans_half_w, trans_half_h
        )
        
        # Конечная точка — на краю круга (не внутри)
        end_pt = QPointF(
            end.x() - r_place * math.cos(angle),
            end.y() - r_place * math.sin(angle)
        )

        self._draw_arrow_line(painter, start_pt, end_pt)
    
    def _intersect_line_with_rect(self, point_outside, rect_center, half_w, half_h):
        """Находит точку пересечения линии с прямоугольником."""
        dx = rect_center.x() - point_outside.x()
        dy = rect_center.y() - point_outside.y()
        
        if dx == 0 and dy == 0:
            return rect_center
        
        # Нормализуем направление
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return rect_center
        
        dx_norm = dx / length
        dy_norm = dy / length
        
        # Находим точку пересечения с границей прямоугольника
        # Проверяем пересечение с каждой стороной
        t_min = float('inf')
        intersection = rect_center
        
        # Левая сторона
        if dx_norm != 0:
            t = (rect_center.x() - half_w - point_outside.x()) / dx_norm
            if t > 0:
                y = point_outside.y() + t * dy_norm
                if abs(y - rect_center.y()) <= half_h:
                    if t < t_min:
                        t_min = t
                        intersection = QPointF(rect_center.x() - half_w, y)
        
        # Правая сторона
        if dx_norm != 0:
            t = (rect_center.x() + half_w - point_outside.x()) / dx_norm
            if t > 0:
                y = point_outside.y() + t * dy_norm
                if abs(y - rect_center.y()) <= half_h:
                    if t < t_min:
                        t_min = t
                        intersection = QPointF(rect_center.x() + half_w, y)
        
        # Верхняя сторона
        if dy_norm != 0:
            t = (rect_center.y() - half_h - point_outside.y()) / dy_norm
            if t > 0:
                x = point_outside.x() + t * dx_norm
                if abs(x - rect_center.x()) <= half_w:
                    if t < t_min:
                        t_min = t
                        intersection = QPointF(x, rect_center.y() - half_h)
        
        # Нижняя сторона
        if dy_norm != 0:
            t = (rect_center.y() + half_h - point_outside.y()) / dy_norm
            if t > 0:
                x = point_outside.x() + t * dx_norm
                if abs(x - rect_center.x()) <= half_w:
                    if t < t_min:
                        t_min = t
                        intersection = QPointF(x, rect_center.y() + half_h)
        
        return intersection

    def _draw_arrow_line(self, painter, start, end):
        painter.drawLine(start, end)

        # Стрелка
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        arrow_size = 8

        # Точка на конце линии
        ex, ey = end.x(), end.y()

        # Две точки "усов" стрелки
        p1 = QPointF(
            ex - arrow_size * math.cos(angle - math.pi / 6),
            ey - arrow_size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            ex - arrow_size * math.cos(angle + math.pi / 6),
            ey - arrow_size * math.sin(angle + math.pi / 6),
        )

        painter.drawLine(end, p1)
        painter.drawLine(end, p2)
    
    def _draw_orthogonal_arrow_place_to_transition(self, painter, p_idx, t_idx, r_place, w_trans, h_trans):
        """Отрисовывает ортогональную (ломаную) стрелку от места к переходу."""
        if p_idx >= len(self.place_positions) or t_idx >= len(self.transition_positions):
            return

        start = self.place_positions[p_idx]
        end_center = self.transition_positions[t_idx]

        # Вычисляем точки для ломаной линии (Manhattan routing)
        # Стартовая точка — на краю круга (справа)
        start_pt = QPointF(start.x() + r_place, start.y())
        
        # Конечная точка — на краю прямоугольника (слева)
        end_pt = QPointF(end_center.x() - w_trans / 2, end_center.y())
        
        # Создаем ломаную: (x1, y1) -> (x_mid, y1) -> (x_mid, y2) -> (x2, y2)
        mid_x = (start_pt.x() + end_pt.x()) / 2
        points = [
            start_pt,
            QPointF(mid_x, start_pt.y()),
            QPointF(mid_x, end_pt.y()),
            end_pt
        ]
        
        # Рисуем ломаную линию
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])
        
        # Рисуем стрелку на конце
        self._draw_arrow_head(painter, points[-2], points[-1])
    
    def _draw_orthogonal_arrow_transition_to_place(self, painter, t_idx, p_idx, r_place, w_trans, h_trans):
        """Отрисовывает ортогональную (ломаную) стрелку от перехода к месту."""
        if p_idx >= len(self.place_positions) or t_idx >= len(self.transition_positions):
            return

        start_center = self.transition_positions[t_idx]
        end = self.place_positions[p_idx]

        # Стартовая точка — на краю прямоугольника (справа)
        start_pt = QPointF(start_center.x() + w_trans / 2, start_center.y())
        
        # Конечная точка — на краю круга (слева)
        end_pt = QPointF(end.x() - r_place, end.y())
        
        # Создаем ломаную: (x1, y1) -> (x_mid, y1) -> (x_mid, y2) -> (x2, y2)
        mid_x = (start_pt.x() + end_pt.x()) / 2
        points = [
            start_pt,
            QPointF(mid_x, start_pt.y()),
            QPointF(mid_x, end_pt.y()),
            end_pt
        ]
        
        # Рисуем ломаную линию
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])
        
        # Рисуем стрелку на конце
        self._draw_arrow_head(painter, points[-2], points[-1])
    
    def _draw_arrow_head(self, painter, from_point, to_point):
        """Рисует наконечник стрелки на конце линии."""
        angle = math.atan2(to_point.y() - from_point.y(), to_point.x() - from_point.x())
        arrow_size = 8

        ex, ey = to_point.x(), to_point.y()

        p1 = QPointF(
            ex - arrow_size * math.cos(angle - math.pi / 6),
            ey - arrow_size * math.sin(angle - math.pi / 6),
        )
        p2 = QPointF(
            ex - arrow_size * math.cos(angle + math.pi / 6),
            ey - arrow_size * math.sin(angle + math.pi / 6),
        )

        painter.drawLine(to_point, p1)
        painter.drawLine(to_point, p2)
    
    # --- Обработка мыши для перетаскивания ---
    
    def mousePressEvent(self, event):
        """Обработчик нажатия кнопки мыши для перетаскивания элементов."""
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            self.drag_start_pos = QPointF(pos.x(), pos.y())
            
            # Проверяем, кликнули ли на место
            place_idx = self._find_place_at(pos)
            if place_idx is not None:
                self.selected_place_idx = place_idx
                self.selected_transition_idx = None
                self.dragging = True
                return
            
            # Проверяем, кликнули ли на переход
            trans_idx = self._find_transition_at(pos)
            if trans_idx is not None:
                self.selected_transition_idx = trans_idx
                self.selected_place_idx = None
                self.dragging = True
                return
    
    def mouseMoveEvent(self, event):
        """Обработчик перемещения мыши для перетаскивания элементов."""
        if self.dragging:
            pos = event.position().toPoint()
            new_pos = QPointF(pos.x(), pos.y())
            
            if self.selected_place_idx is not None:
                if 0 <= self.selected_place_idx < len(self.place_positions):
                    # Обновляем позицию напрямую, без пересчета раскладки
                    self.place_positions[self.selected_place_idx] = new_pos
                    # Убеждаемся, что позиции помечены как инициализированные
                    # чтобы они не пересчитывались при следующем paintEvent
                    if not self.positions_initialized:
                        self.positions_initialized = True
                    self.update()
            
            elif self.selected_transition_idx is not None:
                if 0 <= self.selected_transition_idx < len(self.transition_positions):
                    # Обновляем позицию напрямую, без пересчета раскладки
                    self.transition_positions[self.selected_transition_idx] = new_pos
                    # Убеждаемся, что позиции помечены как инициализированные
                    if not self.positions_initialized:
                        self.positions_initialized = True
                    self.update()
    
    def mouseReleaseEvent(self, event):
        """Обработчик отпускания кнопки мыши."""
        if event.button() == Qt.LeftButton:
            # Сохраняем позиции после перетаскивания
            if self.dragging:
                # Убеждаемся, что позиции помечены как инициализированные
                # чтобы они не пересчитывались при следующем paintEvent
                self.positions_initialized = True
            self.dragging = False
            self.selected_place_idx = None
            self.selected_transition_idx = None
            self.drag_start_pos = None
    
    def _find_place_at(self, pos):
        """Находит место в заданной позиции."""
        if not self.place_positions or len(self.place_positions) == 0:
            return None
        place_radius, _, _ = self._calculate_dynamic_sizes()
        for i, place_pos in enumerate(self.place_positions):
            dx = pos.x() - place_pos.x()
            dy = pos.y() - place_pos.y()
            distance = math.sqrt(dx * dx + dy * dy)
            if distance <= place_radius + 5:  # Небольшой запас для удобства клика
                return i
        return None
    
    def _find_transition_at(self, pos):
        """Находит переход в заданной позиции."""
        if not self.transition_positions or len(self.transition_positions) == 0:
            return None
        _, trans_w, trans_h = self._calculate_dynamic_sizes()
        for i, trans_pos in enumerate(self.transition_positions):
            dx = abs(pos.x() - trans_pos.x())
            dy = abs(pos.y() - trans_pos.y())
            if dx <= trans_w / 2 + 5 and dy <= trans_h / 2 + 5:  # Небольшой запас
                return i
        return None
    
    def resizeEvent(self, event):
        """Обработчик изменения размера виджета."""
        super().resizeEvent(event)
        # При изменении размера НЕ пересчитываем позиции, если идет перетаскивание
        if not self.dragging:
            # Для режимов, которые должны адаптироваться к размеру
            if self.layout_mode == "fsm" and self.positions_initialized:
                # Для FSM просто обновим размер - пересчет произойдет в _compute_layout
                # при следующем paintEvent, если размер действительно изменился
                pass
            elif self.positions_initialized and self.layout_mode in ("hierarchical", "orthogonal", "organic"):
                # Для других режимов сбрасываем инициализацию для пересчета при следующем paintEvent
                self.positions_initialized = False
        # Перерисовываем (но позиции не пересчитаются, если идет перетаскивание)
        self.update()


