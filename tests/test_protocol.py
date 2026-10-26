from elkbleddm import protocol
from elkbleddm.protocol import Dialect


def h(value: str) -> bytes:
    return bytes.fromhex(value)


def test_modern_power():
    assert protocol.power(True, Dialect.MODERN) == h("7e 04 04 01 00 01 ff 00 ef")
    assert protocol.power(False, Dialect.MODERN) == h("7e 04 04 00 00 00 ff 00 ef")


def test_modern_color():
    assert protocol.color(255, 0, 0, Dialect.MODERN) == h(
        "7e 07 05 03 ff 00 00 10 ef"
    )


def test_modern_brightness_effect_speed():
    assert protocol.brightness(255, Dialect.MODERN) == h(
        "7e 04 01 ff ff ff ff 00 ef"
    )
    assert protocol.effect(0, Dialect.MODERN) == h("7e 05 03 80 03 ff ff 00 ef")
    assert protocol.effect(21, Dialect.MODERN) == h("7e 05 03 95 03 ff ff 00 ef")
    assert protocol.effect_speed(255, Dialect.MODERN) == h(
        "7e 04 02 ff ff ff ff 00 ef"
    )


def test_modern_white_and_mic():
    assert protocol.color_temp(100, 50, Dialect.MODERN) == h(
        "7e 06 05 02 64 32 ff 08 ef"
    )
    assert protocol.preset(4, Dialect.MODERN) == h("7e 05 05 01 04 ff ff 08 ef")
    assert protocol.mic(True, Dialect.MODERN) == h("7e 04 07 01 ff ff ff 00 ef")
    assert protocol.mic_sensitivity(128, Dialect.MODERN) == h(
        "7e 04 06 80 ff ff ff 00 ef"
    )
    assert protocol.mic_eq(3, Dialect.MODERN) == h("7e 05 03 83 04 ff ff 00 ef")
    assert protocol.pin_sequence(255, 0, 0, Dialect.MODERN) == h(
        "7e 06 81 ff 00 00 ff 00 ef"
    )


def test_legacy_power_and_color():
    assert protocol.power(True, Dialect.LEGACY) == h("7e 00 04 f0 00 01 ff 00 ef")
    assert protocol.power(False, Dialect.LEGACY) == h("7e 00 04 00 00 00 ff 00 ef")
    assert protocol.color(0x12, 0x34, 0x56, Dialect.LEGACY) == h(
        "7e 00 05 03 12 34 56 00 ef"
    )


def test_legacy_brightness_effect_speed():
    assert protocol.brightness(50, Dialect.LEGACY) == h(
        "7e 00 01 32 00 00 00 00 ef"
    )
    assert protocol.effect(0x87, Dialect.LEGACY) == h(
        "7e 00 03 87 03 00 00 00 ef"
    )
    assert protocol.effect_speed(50, Dialect.LEGACY) == h(
        "7e 00 02 32 00 00 00 00 ef"
    )


def test_legacy_white_preset_and_time():
    assert protocol.color_temp(100, 50, Dialect.LEGACY) == h(
        "7e 00 05 02 64 32 00 00 ef"
    )
    assert protocol.preset(4, Dialect.LEGACY) == h(
        "7e 00 05 01 04 00 00 00 ef"
    )
    assert protocol.sync_time(13, 45, 30, 2) == h(
        "7e 00 83 0d 2d 1e 02 00 ef"
    )


def test_effect_names():
    assert protocol.effects(Dialect.MODERN)["jump_rgb"] == 0
    assert protocol.effects(Dialect.LEGACY)["jump_rgb"] == 0x87


def test_static_mode():
    assert protocol.static_mode() == h("7e 00 05 01 00 00 00 00 ef")


def test_from_hex():
    assert protocol.from_hex("7e 00 ef") == h("7e00ef")
    assert protocol.from_hex("7e:00:ef") == h("7e00ef")
