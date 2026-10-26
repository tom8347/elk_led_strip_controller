import pytest

from elkbleddm.screen import (
    ColorSmoother,
    FRAME_BYTES,
    FRAME_H,
    FRAME_W,
    adjust_color,
    extract_color,
)


def make_frame(pixel):
    buf = bytearray()
    for y in range(FRAME_H):
        for x in range(FRAME_W):
            buf.extend(pixel(x, y))
    assert len(buf) == FRAME_BYTES
    return bytes(buf)


def solid(r, g, b):
    return make_frame(lambda _x, _y: (r, g, b))


def test_average_solid():
    assert extract_color(solid(255, 0, 0), "average") == (255, 0, 0)


def test_average_two_halves():
    frame = make_frame(lambda x, _y: (255, 0, 0) if x < FRAME_W // 2 else (0, 255, 0))
    assert extract_color(frame, "average") == (127, 127, 0)


def test_edge_ignores_centre():
    def pixel(x, y):
        centre = FRAME_W // 4 <= x < FRAME_W * 3 // 4 and FRAME_H // 4 <= y < FRAME_H * 3 // 4
        return (0, 255, 0) if centre else (255, 0, 0)

    assert extract_color(make_frame(pixel), "edge") == (255, 0, 0)


def test_dominant_prefers_saturated_colour():
    def pixel(x, y):
        return (128, 128, 128) if (y * FRAME_W + x) % 10 else (255, 0, 0)

    r, g, b = extract_color(make_frame(pixel), "dominant")
    assert r > g and r > b and r > 200


def test_invalid_mode():
    with pytest.raises(ValueError):
        extract_color(solid(0, 0, 0), "nope")


def test_adjust_color_clamps():
    assert adjust_color((255, 0, 0), saturation=10, gain=10) == (255, 0, 0)
    assert adjust_color((0, 0, 0), saturation=10, gain=10) == (0, 0, 0)


def test_smoother_instant():
    smoother = ColorSmoother(0)
    assert smoother.smooth((255, 0, 0)) == (255, 0, 0)


def test_smoother_gradual():
    smoother = ColorSmoother(0.9)
    smoother.smooth((255, 0, 0))
    r, g, b = smoother.smooth((0, 0, 255))
    assert r > 0 and b > 0
