import re
from typing import Optional

def normalize_phone(phone: str) -> Optional[str]:
    if not phone:
        return None

    # Убираем всё, кроме цифр
    digits = re.sub(r'\D', '', phone)

    # Удаляем код страны 996
    if digits.startswith("996"):
        digits = digits[3:]

    # Если номера нет ведущего нуля — добавим
    if len(digits) == 9:
        digits = "0" + digits

    # Если после всех операций длина не 10 — мусор
    if len(digits) != 10:
        return None

    return digits
