"""UI utilities for dashboard."""

from typing import List


def generate_braille_sparkline(data_list: List[float], width: int = 25, max_val: float = 0.0) -> str:
    """Generate a smooth Braille-based sparkline string."""
    if not data_list:
        return " " * width

    # We need 2 samples per character width
    num_samples = width * 2
    data = data_list[-num_samples:]
    if len(data) < num_samples:
        data = [0.0] * (num_samples - len(data)) + data

    local_max = max(data)
    if max_val > 0:
        scale = max_val
    else:
        scale = local_max if local_max > 0 else 1.0

    def get_char(v1, v2):
        # v1, v2 are values
        left_dots = [0, 0, 0, 0]  # rows 1,2,3,7
        right_dots = [0, 0, 0, 0]  # rows 4,5,6,8

        # Map value to 0..4 dots
        l_level = int((v1 / scale) * 4)
        r_level = int((v2 / scale) * 4)

        # Clamp
        l_level = max(0, min(l_level, 4))
        r_level = max(0, min(r_level, 4))

        for i in range(l_level):
            left_dots[3 - i] = 1
        for i in range(r_level):
            right_dots[3 - i] = 1

        # Map dots to Braille bitmask
        # 1:0x01, 2:0x02, 3:0x04, 4:0x08, 5:0x10, 6:0x20, 7:0x40, 8:0x80
        mask = 0
        if left_dots[0]:
            mask |= 0x01
        if left_dots[1]:
            mask |= 0x02
        if left_dots[2]:
            mask |= 0x04
        if left_dots[3]:
            mask |= 0x40

        if right_dots[0]:
            mask |= 0x08
        if right_dots[1]:
            mask |= 0x10
        if right_dots[2]:
            mask |= 0x20
        if right_dots[3]:
            mask |= 0x80

        if mask == 0:
            return " "
        return chr(0x2800 + mask)

    result = ""
    for i in range(0, num_samples, 2):
        result += get_char(data[i], data[i + 1])

    return result
