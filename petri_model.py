import random


class PetriNetModel:
    """Модель ординарной сети Петри на P местах и T переходах."""

    def __init__(self, num_places: int = 7, num_transitions: int = 5):
        self.P = num_places
        self.T = num_transitions
        self.M = [0] * self.P  # Текущая разметка (marking)
        self.W_in = [[0] * self.P for _ in range(self.T)]  # Входная матрица (Переход -> Место)
        self.W_out = [[0] * self.P for _ in range(self.T)]  # Выходная матрица (Переход -> Место)
        self.MAX_TOKENS = 3  # Максимальное число меток в месте

    # --- Генерация сети и разметки ---

    def generate_random_net(self) -> None:
        """Генерирует случайную, но корректную ординарную сеть."""
        # Все веса должны быть 0 или 1 (ординарная сеть).
        # Каждая строка W_in и W_out должна содержать хотя бы одну единицу.
        for j in range(self.T):
            # Входные дуги (W_in)
            for i in range(self.P):
                self.W_in[j][i] = random.choice([0, 1])

            if sum(self.W_in[j]) == 0:
                self.W_in[j][random.randint(0, self.P - 1)] = 1

            # Выходные дуги (W_out)
            for i in range(self.P):
                self.W_out[j][i] = random.choice([0, 1])

            if sum(self.W_out[j]) == 0:
                self.W_out[j][random.randint(0, self.P - 1)] = 1

    def generate_random_marking(self) -> None:
        """Генерирует случайную начальную разметку (0..MAX_TOKENS)."""
        self.M = [random.randint(0, self.MAX_TOKENS) for _ in range(self.P)]

    # --- Логика срабатывания ---

    def is_enabled(self, t_index: int) -> bool:
        """Проверяет, разрешен ли переход t_index к срабатыванию."""
        for i in range(self.P):
            if self.M[i] < self.W_in[t_index][i]:
                return False
        return True

    def fire_transitions(self, t_indices) -> bool:
        """Выполняет срабатывание заданного подмножества переходов."""
        required = [0] * self.P
        for t_idx in t_indices:
            for i in range(self.P):
                required[i] += self.W_in[t_idx][i]

        # Проверяем, что суммарное потребление фишек не превышает текущую разметку
        for i in range(self.P):
            if self.M[i] < required[i]:
                return False

        # Снимаем фишки
        for t_idx in t_indices:
            for i in range(self.P):
                self.M[i] -= self.W_in[t_idx][i]

        # Добавляем фишки (с учётом MAX_TOKENS)
        for t_idx in t_indices:
            for i in range(self.P):
                self.M[i] = min(self.MAX_TOKENS, self.M[i] + self.W_out[t_idx][i])

        return True

    def step(self) -> str:
        """Выполняет один шаг работы (конкурентно и параллельно)."""
        enabled_transitions = [i for i in range(self.T) if self.is_enabled(i)]

        if not enabled_transitions:
            return "Нет разрешенных переходов. Сеть заблокирована."

        # Выбираем максимальное неконфликтующее подмножество (параллельность)
        firing_set = []
        available_t = set(enabled_transitions)

        while available_t:
            t_idx = random.choice(list(available_t))
            firing_set.append(t_idx)
            available_t.remove(t_idx)

            # Удаляем конфликтующие переходы (общие входные места)
            conflicting_t = set()
            for other_t_idx in available_t:
                conflict = False
                for i in range(self.P):
                    if self.W_in[t_idx][i] == 1 and self.W_in[other_t_idx][i] == 1:
                        conflict = True
                        break
                if conflict:
                    conflicting_t.add(other_t_idx)

            available_t -= conflicting_t

        self.fire_transitions(firing_set)
        return f"Сработали переходы: {firing_set}"

    # --- Сериализация в словарь ---

    def to_dict(self) -> dict:
        """Преобразует модель в словарь (удобно для UI / отладки)."""
        return {
            "num_places": self.P,
            "num_transitions": self.T,
            "marking": self.M,
            "W_in": self.W_in,
            "W_out": self.W_out,
        }

    def from_dict(self, data: dict) -> None:
        """Загружает модель из словаря."""
        if data["num_places"] != self.P or data["num_transitions"] != self.T:
            raise ValueError("Несоответствие размерности сети")
        self.M = data["marking"]
        self.W_in = data["W_in"]
        self.W_out = data["W_out"]


