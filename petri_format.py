from __future__ import annotations

from typing import List, Dict, Any

from petri_model import PetriNetModel


def format_petri_to_text(model: PetriNetModel) -> str:
    """Формирует человекочитаемое текстовое представление сети Петри.

    Формат:
    Marking:
    M: 3 0 3 1 1 0 2

    W_in:
        p1 p2 ... p7
    t1: 0 1 ...

    W_out:
        p1 p2 ... p7
    t1: ...
    """
    lines: List[str] = []

    # Разметка
    lines.append("Marking:")
    lines.append("M: " + " ".join(str(x) for x in model.M))
    lines.append("")

    # Входная матрица
    header = "    " + " ".join(f"p{i+1}" for i in range(model.P))
    lines.append("W_in:")
    lines.append(header)
    for t in range(model.T):
        row = " ".join(str(model.W_in[t][p]) for p in range(model.P))
        lines.append(f"t{t+1}: {row}")
    lines.append("")

    # Выходная матрица
    lines.append("W_out:")
    lines.append(header)
    for t in range(model.T):
        row = " ".join(str(model.W_out[t][p]) for p in range(model.P))
        lines.append(f"t{t+1}: {row}")

    return "\n".join(lines) + "\n"


def parse_petri_from_text(text: str, expected_P: int, expected_T: int, max_tokens: int) -> Dict[str, Any]:
    """Парсит текстовый формат сети Петри и возвращает словарь, совместимый с PetriNetModel.to_dict()."""
    lines = [line.rstrip() for line in text.splitlines()]

    # Убираем полностью пустые строки для удобства проверки
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        raise ValueError("Файл пуст.")

    # --- Marking ---
    m_idx = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        # Ищем именно строку формата "M: ..." (а не "Marking:")
        if stripped.lower().startswith("m:"):
            m_idx = idx
            break
    if m_idx is None:
        raise ValueError("Не найдена строка разметки вида 'M: v1 v2 ... vP'.")

    m_line = lines[m_idx].strip()
    try:
        after_colon = m_line.split(":", 1)[1]
    except IndexError:
        raise ValueError("Строка с разметкой должна иметь вид 'M: v1 v2 ... vP'.")
    try:
        marking_vals = [int(x) for x in after_colon.split()]
    except ValueError:
        raise ValueError("Все значения в строке 'M:' должны быть целыми числами.")

    if len(marking_vals) != expected_P:
        raise ValueError(f"В разметке M должно быть {expected_P} значений, найдено {len(marking_vals)}.")
    for i, tok in enumerate(marking_vals):
        if tok < 0 or tok > max_tokens:
            raise ValueError(
                f"Разметка места p{i+1} должна быть в диапазоне 0..{max_tokens}, найдено {tok}."
            )

    def find_line_starting(prefix: str) -> int:
        for idx, line in enumerate(lines):
            if line.strip().lower().startswith(prefix.lower()):
                return idx
        raise ValueError(f"Не найдена строка, начинающаяся с '{prefix}'.")

    # --- W_in ---
    win_block_idx = find_line_starting("W_in")
    header_idx = win_block_idx + 1
    if header_idx >= len(lines):
        raise ValueError("После 'W_in:' ожидается строка с заголовками p1..pP.")

    rows_start = header_idx + 1
    if rows_start + expected_T > len(lines) + 1:
        raise ValueError(f"После заголовка W_in ожидается {expected_T} строк t1..t{expected_T}.")

    W_in: List[List[int]] = []
    for t in range(expected_T):
        line = lines[rows_start + t].strip()
        if not line:
            raise ValueError(f"Строка t{t+1} в блоке W_in пуста.")
        if ":" not in line:
            raise ValueError(f"Строка t{t+1} в блоке W_in должна иметь вид 't{t+1}: v1 ... vP'.")
        prefix, data_part = line.split(":", 1)
        prefix = prefix.strip().lower()
        if prefix != f"t{t+1}":
            raise ValueError(f"Ожидалась строка 't{t+1}: ...' в блоке W_in, найдено '{line}'.")
        try:
            nums = [int(x) for x in data_part.split()]
        except ValueError:
            raise ValueError(f"Все элементы строки t{t+1} в W_in должны быть целыми числами 0 или 1.")
        if len(nums) != expected_P:
            raise ValueError(
                f"В строке t{t+1} блока W_in должно быть {expected_P} значений, найдено {len(nums)}."
            )
        for p_idx, val in enumerate(nums):
            if val not in (0, 1):
                raise ValueError(
                    f"W_in[t{t+1}][p{p_idx+1}] должно быть 0 или 1 (ординарная сеть). Найдено {val}."
                )
        if sum(nums) == 0:
            raise ValueError(f"Переход t{t+1} в W_in не связан ни с одним местом (строка из одних нулей).")
        W_in.append(nums)

    # --- W_out ---
    wout_block_idx = find_line_starting("W_out")
    header_idx = wout_block_idx + 1
    if header_idx >= len(lines):
        raise ValueError("После 'W_out:' ожидается строка с заголовками p1..pP.")

    rows_start = header_idx + 1
    if rows_start + expected_T > len(lines) + 1:
        raise ValueError(f"После заголовка W_out ожидается {expected_T} строк t1..t{expected_T}.")

    W_out: List[List[int]] = []
    for t in range(expected_T):
        line = lines[rows_start + t].strip()
        if not line:
            raise ValueError(f"Строка t{t+1} в блоке W_out пуста.")
        if ":" not in line:
            raise ValueError(f"Строка t{t+1} в блоке W_out должна иметь вид 't{t+1}: v1 ... vP'.")
        prefix, data_part = line.split(":", 1)
        prefix = prefix.strip().lower()
        if prefix != f"t{t+1}":
            raise ValueError(f"Ожидалась строка 't{t+1}: ...' в блоке W_out, найдено '{line}'.")
        try:
            nums = [int(x) for x in data_part.split()]
        except ValueError:
            raise ValueError(f"Все элементы строки t{t+1} в W_out должны быть целыми числами 0 или 1.")
        if len(nums) != expected_P:
            raise ValueError(
                f"В строке t{t+1} блока W_out должно быть {expected_P} значений, найдено {len(nums)}."
            )
        for p_idx, val in enumerate(nums):
            if val not in (0, 1):
                raise ValueError(
                    f"W_out[t{t+1}][p{p_idx+1}] должно быть 0 или 1 (ординарная сеть). Найдено {val}."
                )
        if sum(nums) == 0:
            raise ValueError(f"Переход t{t+1} в W_out не связан ни с одним местом (строка из одних нулей).")
        W_out.append(nums)

    return {
        "num_places": expected_P,
        "num_transitions": expected_T,
        "marking": marking_vals,
        "W_in": W_in,
        "W_out": W_out,
    }


