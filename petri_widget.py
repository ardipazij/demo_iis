from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from PySide6.QtCore import Qt, QPointF


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

        # Предрасчёт простой схемы расположения:
        # 7 мест в верхнем ряду, 5 переходов в нижнем ряду.
        self.place_positions = []
        self.transition_positions = []

    def set_model(self, model):
        """Позволяет заменить модель (если её перезагружают)."""
        self.model = model
        self.update()

    # --- Геометрия ---

    def _compute_layout(self):
        """Рассчитывает координаты мест и переходов в зависимости от размера виджета."""
        width = self.width()
        height = self.height()

        # Отступы по краям
        margin_x = 60
        margin_y = 40

        # Радиус места и размеры перехода
        place_radius = 18
        trans_width = 24
        trans_height = 60

        # Горизонтальное распределение мест и переходов по всей ширине
        # 7 мест, 5 переходов — выравниваем по равным промежуткам
        self.place_positions = []
        self.transition_positions = []

        if self.model is None:
            return place_radius, trans_width, trans_height

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

        return place_radius, trans_width, trans_height

    # --- Рисование ---

    def paintEvent(self, event):
        if self.model is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

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

        # Стартовая точка — низ круга
        start_pt = QPointF(start.x(), start.y() + r_place)
        # Конечная точка — верх прямоугольника
        end_pt = QPointF(end_center.x(), end_center.y() - h_trans / 2)

        self._draw_arrow_line(painter, start_pt, end_pt)

    def _draw_arrow_transition_to_place(self, painter, t_idx, p_idx, r_place, w_trans, h_trans):
        if p_idx >= len(self.place_positions) or t_idx >= len(self.transition_positions):
            return

        start_center = self.transition_positions[t_idx]
        end = self.place_positions[p_idx]

        # Старт — низ прямоугольника
        start_pt = QPointF(start_center.x(), start_center.y() + h_trans / 2)
        # Конец — верх круга
        end_pt = QPointF(end.x(), end.y() - r_place)

        self._draw_arrow_line(painter, start_pt, end_pt)

    def _draw_arrow_line(self, painter, start, end):
        painter.drawLine(start, end)

        # Стрелка
        import math

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


