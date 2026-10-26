"""Packet builders for the ELK-BLEDDM / ELK-BLEDOM protocol.

Two dialects exist in the wild:

* ``modern``  - frame is ``7E LEN CMD ... EF`` and is what the Lotus Lantern
  app (``com.easylink.colorful``) sends to ELK-BLEDDM units.
* ``legacy``  - original ELK-BLEDOM framing, ``7E 00 CMD ... EF``.

Both use service ``0000fff0-...`` and write characteristic ``0000fff3-...``.
"""

from __future__ import annotations

from enum import Enum

HEADER = 0x7E
FOOTER = 0xEF

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_CHARACTERISTIC_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
NOTIFY_CHARACTERISTIC_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"


class Dialect(str, Enum):
    MODERN = "modern"
    LEGACY = "legacy"


# Modern effect ids are the low 7 bits; the app ORs 0x80 on the wire.
EFFECTS_MODERN: dict[str, int] = {
    "jump_rgb": 0,
    "jump_seven": 1,
    "crossfade_rgb": 2,
    "crossfade_seven": 3,
    "crossfade_red": 4,
    "crossfade_green": 5,
    "crossfade_blue": 6,
    "crossfade_yellow": 7,
    "crossfade_cyan": 8,
    "crossfade_magenta": 9,
    "crossfade_white": 10,
    "crossfade_red_green": 11,
    "crossfade_red_blue": 12,
    "crossfade_green_blue": 13,
    "strobe_red": 14,
    "strobe_green": 15,
    "strobe_blue": 16,
    "strobe_yellow": 17,
    "strobe_cyan": 18,
    "strobe_magenta": 19,
    "strobe_white": 20,
    "strobe_seven": 21,
}

# Legacy (ELK-BLEDOM) effect ids already include the 0x80 flag.
EFFECTS_LEGACY: dict[str, int] = {
    "jump_rgb": 0x87,
    "jump_seven": 0x88,
    "crossfade_rgb": 0x89,
    "crossfade_seven": 0x8A,
    "crossfade_red": 0x8B,
    "crossfade_green": 0x8C,
    "crossfade_blue": 0x8D,
    "crossfade_yellow": 0x8E,
    "crossfade_cyan": 0x8F,
    "crossfade_magenta": 0x90,
    "crossfade_white": 0x91,
    "crossfade_red_green": 0x92,
    "crossfade_red_blue": 0x93,
    "crossfade_green_blue": 0x94,
    "strobe_red": 0x96,
    "strobe_green": 0x97,
    "strobe_blue": 0x98,
    "strobe_yellow": 0x99,
    "strobe_cyan": 0x9A,
    "strobe_magenta": 0x9B,
    "strobe_white": 0x9C,
    "strobe_seven": 0x95,
}


def effects(dialect: Dialect | str) -> dict[str, int]:
    return EFFECTS_LEGACY if Dialect(dialect) is Dialect.LEGACY else EFFECTS_MODERN


def clamp(value: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, int(value)))


def _frame(*payload: int) -> bytes:
    return bytes((HEADER, *payload, FOOTER))


def power(on: bool, dialect: Dialect | str = Dialect.MODERN) -> bytes:
    """Turn the strip on or off."""
    state = 0x01 if on else 0x00
    if Dialect(dialect) is Dialect.LEGACY:
        # 7E 00 04 [F0/00] 00 [01/00] FF 00 EF
        return _frame(0x00, 0x04, 0xF0 if on else 0x00, 0x00, state, 0xFF, 0x00)
    # 7E 04 04 [01/00] 00 [01/00] FF 00 EF
    return _frame(0x04, 0x04, state, 0x00, state, 0xFF, 0x00)


def color(r: int, g: int, b: int, dialect: Dialect | str = Dialect.MODERN) -> bytes:
    """Set a static RGB colour (0-255 per channel)."""
    r, g, b = clamp(r), clamp(g), clamp(b)
    if Dialect(dialect) is Dialect.LEGACY:
        return _frame(0x00, 0x05, 0x03, r, g, b, 0x00)
    return _frame(0x07, 0x05, 0x03, r, g, b, 0x10)


def brightness(value: int, dialect: Dialect | str = Dialect.MODERN) -> bytes:
    """Set brightness using the native 0-255 modern / 0-100 legacy byte."""
    value = clamp(value)
    if Dialect(dialect) is Dialect.LEGACY:
        return _frame(0x00, 0x01, value, 0x00, 0x00, 0x00, 0x00)
    return _frame(0x04, 0x01, value, 0xFF, 0xFF, 0xFF, 0x00)


def effect(code: int, dialect: Dialect | str = Dialect.MODERN) -> bytes:
    """Select an effect by raw code (modern uses 0-21, legacy 0x87-0x9C)."""
    code = clamp(code)
    if Dialect(dialect) is Dialect.LEGACY:
        return _frame(0x00, 0x03, code, 0x03, 0x00, 0x00, 0x00)
    flagged = (code & 0x7F) | 0x80
    return _frame(0x05, 0x03, flagged, 0x03, 0xFF, 0xFF, 0x00)


def effect_speed(value: int, dialect: Dialect | str = Dialect.MODERN) -> bytes:
    value = clamp(value)
    if Dialect(dialect) is Dialect.LEGACY:
        return _frame(0x00, 0x02, value, 0x00, 0x00, 0x00, 0x00)
    return _frame(0x04, 0x02, value, 0xFF, 0xFF, 0xFF, 0x00)


def color_temp(
    warm: int, cold: int, dialect: Dialect | str = Dialect.MODERN
) -> bytes:
    warm, cold = clamp(warm), clamp(cold)
    if Dialect(dialect) is Dialect.LEGACY:
        return _frame(0x00, 0x05, 0x02, warm, cold, 0x00, 0x00)
    return _frame(0x06, 0x05, 0x02, warm, cold, 0xFF, 0x08)


def preset(index: int, dialect: Dialect | str = Dialect.MODERN) -> bytes:
    index = clamp(index)
    if Dialect(dialect) is Dialect.LEGACY:
        return _frame(0x00, 0x05, 0x01, index, 0x00, 0x00, 0x00)
    return _frame(0x05, 0x05, 0x01, index, 0xFF, 0xFF, 0x08)


def mic(on: bool, dialect: Dialect | str = Dialect.MODERN) -> bytes:
    """Modern-only onboard microphone streaming switch."""
    if Dialect(dialect) is Dialect.LEGACY:
        raise ValueError("microphone control is only defined for the modern dialect")
    return _frame(0x04, 0x07, 0x01 if on else 0x00, 0xFF, 0xFF, 0xFF, 0x00)


def mic_sensitivity(
    value: int, dialect: Dialect | str = Dialect.MODERN
) -> bytes:
    if Dialect(dialect) is Dialect.LEGACY:
        raise ValueError("microphone control is only defined for the modern dialect")
    return _frame(0x04, 0x06, clamp(value), 0xFF, 0xFF, 0xFF, 0x00)


def mic_eq(code: int, dialect: Dialect | str = Dialect.MODERN) -> bytes:
    if Dialect(dialect) is Dialect.LEGACY:
        raise ValueError("microphone control is only defined for the modern dialect")
    flagged = (clamp(code) & 0x7F) | 0x80
    return _frame(0x05, 0x03, flagged, 0x04, 0xFF, 0xFF, 0x00)


def pin_sequence(
    r: int, g: int, b: int, dialect: Dialect | str = Dialect.MODERN
) -> bytes:
    if Dialect(dialect) is Dialect.LEGACY:
        raise ValueError("pin sequence is only defined for the modern dialect")
    return _frame(0x06, 0x81, clamp(r), clamp(g), clamp(b), 0xFF, 0x00)


def sync_time(
    hour: int, minute: int, second: int, day_of_week: int
) -> bytes:
    """Legacy ELK-BLEDOM clock sync (day_of_week: 1=Monday)."""
    return _frame(
        0x00,
        0x83,
        clamp(hour, 0, 23),
        clamp(minute, 0, 59),
        clamp(second, 0, 59),
        clamp(day_of_week, 1, 7),
        0x00,
    )


def static_mode() -> bytes:
    """Leave effect mode and return to a static colour.

    This is the BLEDDM ``7E 00 05 01 ...`` command. It also prevents a new
    effect from starting until the controller is power-cycled, so use it as a
    "stop animation" command rather than a general reset.
    """
    return _frame(0x00, 0x05, 0x01, 0x00, 0x00, 0x00, 0x00)


def from_hex(text: str) -> bytes:
    cleaned = text.replace("0x", "").replace(" ", "").replace(":", "").replace(",", "")
    if len(cleaned) % 2:
        raise ValueError("hex payload must contain an even number of digits")
    return bytes.fromhex(cleaned)
