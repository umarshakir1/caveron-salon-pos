"""Code 128B bars for on-screen slips and graphic printing."""

from __future__ import annotations

# Bar/space widths. Index 103/104/105 are start A/B/C. Index 106 is stop.
PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
]

if len(PATTERNS) != 107:
    raise RuntimeError(f"Code 128 table has {len(PATTERNS)} entries, expected 107.")


def code128_modules(text: str) -> list[tuple[bool, int]]:
    """Return (is_bar, width) pairs including quiet-free start, data, checksum, and stop."""
    values = [104]
    for char in text or "-":
        code = ord(char)
        if code < 32 or code > 126:
            code = ord("-")
        values.append(code - 32)
    checksum = values[0]
    for index, value in enumerate(values[1:], start=1):
        checksum += index * value
    values.append(checksum % 103)
    values.append(106)
    modules: list[tuple[bool, int]] = []
    for value in values:
        is_bar = True
        for width in PATTERNS[value]:
            modules.append((is_bar, int(width)))
            is_bar = not is_bar
    return modules
