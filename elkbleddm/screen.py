"""Ambilight-style screen sync for a single-zone ELK-BLEDDM strip.

Capture is done with ``wf-recorder`` (wlroots screencopy) piped as small
raw RGB frames. The strip is analogue RGB, so the whole strip follows one
colour: the screen average, the screen edges, or a saturation-weighted
dominant colour.
"""

from __future__ import annotations

import asyncio
import colorsys
import json
import logging
import sys
from dataclasses import dataclass

from .controller import ELKStrip

log = logging.getLogger(__name__)

FRAME_W = 64
FRAME_H = 36
FRAME_BYTES = FRAME_W * FRAME_H * 3
MAX_FPS = 120


@dataclass
class ScreenOptions:
    fps: int = 60
    duration: float = 0.0
    mode: str = "average"
    region: str = "full"
    geometry: str | None = None
    smoothing: float = 0.2
    saturation: float = 1.3
    gain: float = 1.0
    min_change: int = 4
    power_every: float = 0.0
    stats: bool = False


@dataclass
class ScreenStats:
    frames: int = 0
    sends: int = 0
    elapsed: float = 0.0

    def summary(self) -> str:
        fps = self.frames / self.elapsed if self.elapsed else 0.0
        return (
            f"frames={self.frames} sends={self.sends} "
            f"elapsed={self.elapsed:.1f}s avg_fps={fps:.1f}"
        )


async def active_window_geometry() -> str | None:
    """Return Hyprland's focused window as grim/wf-recorder geometry."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "hyprctl",
            "-j",
            "activewindow",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        data = json.loads(out)
        at = data.get("at") or [0, 0]
        size = data.get("size") or [0, 0]
        if size[0] <= 0 or size[1] <= 0:
            return None
        return f"{at[0]},{at[1]} {size[0]}x{size[1]}"
    except Exception as exc:  # noqa: BLE001 - best effort
        log.debug("hyprctl activewindow failed: %s", exc)
        return None


class ScreenCapture:
    """A wf-recorder subprocess producing fixed-size raw RGB frames."""

    def __init__(
        self,
        fps: int = 30,
        geometry: str | None = None,
    ) -> None:
        self.fps = max(1, min(MAX_FPS, int(fps)))
        self.geometry = geometry
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None

    @property
    def exit_code(self) -> int | None:
        return self._proc.returncode if self._proc else None

    async def start(self) -> None:
        cmd = [
            "wf-recorder",
            "-D",
            "-r",
            str(self.fps),
            "-c",
            "rawvideo",
            "-x",
            "rgb24",
            "-m",
            "rawvideo",
            "-F",
            f"scale={FRAME_W}:{FRAME_H}",
            "-f",
            "/dev/stdout",
        ]
        if self.geometry:
            cmd[1:1] = ["-g", self.geometry]
        log.debug("starting capture: %s", " ".join(cmd))
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "wf-recorder not found; install it or use the packaged `elk`"
            ) from exc
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        while True:
            line = await self._proc.stderr.readline()
            if not line:
                return
            log.debug("wf-recorder: %s", line.decode(errors="replace").rstrip())

    async def read_frame(self) -> bytes | None:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            return await self._proc.stdout.readexactly(FRAME_BYTES)
        except asyncio.IncompleteReadError:
            return None

    async def stop(self) -> None:
        if self._proc is not None and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except (asyncio.CancelledError, Exception):
                pass
            self._stderr_task = None


def extract_color(frame: bytes, mode: str = "average") -> tuple[int, int, int]:
    """Extract one RGB colour from a FRAME_W x FRAME_H RGB24 frame."""
    if len(frame) != FRAME_BYTES:
        raise ValueError(f"expected {FRAME_BYTES} bytes, got {len(frame)}")

    if mode == "average":
        n = FRAME_W * FRAME_H
        return (
            sum(frame[0::3]) // n,
            sum(frame[1::3]) // n,
            sum(frame[2::3]) // n,
        )

    if mode == "edge":
        edge_x = max(1, int(FRAME_W * 0.25))
        edge_y = max(1, int(FRAME_H * 0.25))
        rs = gs = bs = n = 0
        for y in range(FRAME_H):
            y_edge = y < edge_y or y >= FRAME_H - edge_y
            row = y * FRAME_W * 3
            for x in range(FRAME_W):
                if y_edge or x < edge_x or x >= FRAME_W - edge_x:
                    i = row + x * 3
                    rs += frame[i]
                    gs += frame[i + 1]
                    bs += frame[i + 2]
                    n += 1
        if n:
            return rs // n, gs // n, bs // n
        return extract_color(frame, "average")

    if mode == "dominant":
        rs = gs = bs = total = 0.0
        for i in range(0, len(frame), 3):
            r, g, b = frame[i], frame[i + 1], frame[i + 2]
            max_c = max(r, g, b)
            if max_c == 0:
                continue
            sat = (max_c - min(r, g, b)) / max_c
            if sat < 0.15:
                continue
            weight = sat * (max_c / 255.0)
            rs += r * weight
            gs += g * weight
            bs += b * weight
            total += weight
        if total > 1e-6:
            return round(rs / total), round(gs / total), round(bs / total)
        return extract_color(frame, "average")

    raise ValueError("mode must be one of: average, edge, dominant")


def adjust_color(
    rgb: tuple[int, int, int],
    saturation: float = 1.0,
    gain: float = 1.0,
) -> tuple[int, int, int]:
    r, g, b = (min(255.0, max(0.0, c * gain)) for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    s = min(1.0, max(0.0, s * saturation))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return round(r * 255), round(g * 255), round(b * 255)


class ColorSmoother:
    """Exponential moving average in HSV space (hue wraps correctly)."""

    def __init__(self, smoothing: float = 0.0) -> None:
        smoothing = min(1.0, max(0.0, smoothing))
        self.alpha = 1.0 if smoothing <= 0.0 else max(0.01, 1.0 - smoothing)
        self._h: float | None = None
        self._s = 0.0
        self._v = 0.0

    def reset(self) -> None:
        self._h = None

    def smooth(self, rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        h, s, v = colorsys.rgb_to_hsv(*(c / 255.0 for c in rgb))
        if self._h is None:
            self._h, self._s, self._v = h, s, v
        else:
            dh = h - self._h
            if dh > 0.5:
                dh -= 1.0
            elif dh < -0.5:
                dh += 1.0
            self._h = (self._h + self.alpha * dh) % 1.0
            self._s += self.alpha * (s - self._s)
            self._v += self.alpha * (v - self._v)
        r, g, b = colorsys.hsv_to_rgb(self._h, self._s, self._v)
        return round(r * 255), round(g * 255), round(b * 255)


async def run_screen(strip: ELKStrip, opts: ScreenOptions) -> ScreenStats:
    geometry = opts.geometry
    if opts.region == "focused" and geometry is None:
        geometry = await active_window_geometry()
        if geometry is None:
            log.warning("could not read focused window; capturing full screen")

    capture = ScreenCapture(fps=opts.fps, geometry=geometry)
    smoother = ColorSmoother(opts.smoothing)
    await capture.start()

    loop = asyncio.get_running_loop()
    start = loop.time()
    frames = 0
    sends = 0
    last_color: tuple[int, int, int] | None = None
    last_power = start
    stats = ScreenStats()

    try:
        while True:
            elapsed = loop.time() - start
            if opts.duration > 0 and elapsed >= opts.duration:
                break

            frame = await capture.read_frame()
            if frame is None:
                raise RuntimeError(
                    "wf-recorder stopped "
                    f"(exit {capture.exit_code}); run with -v for details"
                )

            # Colour writes don't power the strip on, so if it was switched
            # off (remote, app, power cut) it would stay dark; re-send power-on
            # now and then, and the current colour straight after it
            if opts.power_every > 0 and loop.time() - last_power >= opts.power_every:
                last_power = loop.time()
                try:
                    await strip.set_power(True)
                    last_color = None
                except Exception as exc:  # noqa: BLE001 - keep the loop alive
                    log.warning("LED power-on failed: %s", exc)

            raw = extract_color(frame, opts.mode)
            rgb = adjust_color(raw, opts.saturation, opts.gain)
            out = smoother.smooth(rgb)
            frames += 1

            changed = last_color is None or sum(
                abs(a - b) for a, b in zip(out, last_color)
            ) >= opts.min_change
            if changed:
                try:
                    await strip.set_color(*out, settle=0.0)
                    sends += 1
                    last_color = out
                except Exception as exc:  # noqa: BLE001 - keep the loop alive
                    log.warning("LED write failed: %s", exc)
                    await asyncio.sleep(0.5)

            if opts.stats and frames % max(1, opts.fps) == 0:
                rate = frames / max(0.001, loop.time() - start)
                print(
                    f"\rframes={frames} fps={rate:.1f} sends={sends}",
                    end="",
                    file=sys.stderr,
                )
    finally:
        await capture.stop()
        stats.frames = frames
        stats.sends = sends
        stats.elapsed = loop.time() - start
        if opts.stats:
            print(f"\n{stats.summary()}", file=sys.stderr)

    return stats
