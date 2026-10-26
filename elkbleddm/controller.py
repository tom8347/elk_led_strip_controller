"""Async controller for ELK-BLEDDM / ELK-BLEDOM BLE LED strips."""

from __future__ import annotations

import asyncio
import colorsys
import logging
import math
from typing import Any

from bleak import BleakClient, BleakScanner

from . import protocol
from .protocol import (
    Dialect,
    SERVICE_UUID,
    WRITE_CHARACTERISTIC_UUID,
)

log = logging.getLogger(__name__)


def rgb_from_text(text: str) -> tuple[int, int, int]:
    value = text.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError("colour must look like #rrggbb or rrggbb")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


class ELKStrip:
    """Owns one BLE connection and exposes the strip's controls."""

    def __init__(
        self,
        address: str | None = None,
        name_prefix: str = "ELK-BLEDDM",
        dialect: Dialect | str = Dialect.MODERN,
        timeout: float = 10.0,
        command_delay: float = 0.3,
        verbose: bool = False,
    ) -> None:
        self.address = address
        self.name_prefix = name_prefix
        self.dialect = Dialect(dialect)
        self.timeout = timeout
        self.command_delay = command_delay
        self.verbose = verbose
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._response = False

    async def __aenter__(self) -> "ELKStrip":
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()

    @staticmethod
    async def discover(timeout: float = 6.0) -> list[Any]:
        devices = await BleakScanner.discover(timeout=timeout)
        return sorted(
            (d for d in devices if d.name),
            key=lambda d: d.name.lower(),
        )

    @classmethod
    async def find(
        cls, name_prefix: str = "ELK-BLEDDM", timeout: float = 6.0
    ) -> str:
        log.info("scanning %.0fs for %r", timeout, name_prefix)
        devices = await BleakScanner.discover(timeout=timeout)
        matches = [
            d for d in devices if (d.name or "").upper().startswith(name_prefix.upper())
        ]
        if not matches:
            names = ", ".join(f"{d.name} ({d.address})" for d in devices if d.name)
            raise RuntimeError(
                f"no BLE device matching {name_prefix!r}; saw: {names or 'nothing'}"
            )
        if len(matches) > 1:
            log.warning(
                "multiple matches, using %s (%s): %s",
                matches[0].name,
                matches[0].address,
                ", ".join(m.address for m in matches),
            )
        return matches[0].address

    async def _resolve_address(self) -> str:
        if self.address:
            return self.address
        self.address = await self.find(self.name_prefix, self.timeout)
        return self.address

    async def connect(self) -> None:
        if self._client is not None and self._client.is_connected:
            return
        address = await self._resolve_address()
        log.info("connecting to %s", address)
        client = BleakClient(address, timeout=self.timeout)
        await client.connect()
        self._client = client

        char = client.services.get_characteristic(WRITE_CHARACTERISTIC_UUID)
        if char is None:
            services = [
                f"{s.uuid}: {', '.join(c.uuid for c in s.characteristics)}"
                for s in client.services
            ]
            await client.disconnect()
            self._client = None
            raise RuntimeError(
                "write characteristic "
                f"{WRITE_CHARACTERISTIC_UUID} not found; services: {services}"
            )
        self._response = "write-without-response" not in char.properties
        log.info("connected to %s (write response=%s)", address, self._response)

    async def disconnect(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            finally:
                self._client = None

    async def ensure_connected(self) -> None:
        if self._client is None or not self._client.is_connected:
            await self.connect()

    async def _send(self, payload: bytes, delay: float | None = None) -> None:
        await self.ensure_connected()
        assert self._client is not None
        async with self._lock:
            if self.verbose:
                print(f"TX {payload.hex(' ')}")
            await self._client.write_gatt_char(
                WRITE_CHARACTERISTIC_UUID,
                payload,
                response=self._response,
            )
            settle = self.command_delay if delay is None else delay
            if settle:
                await asyncio.sleep(settle)

    async def send_raw(self, payload: bytes) -> None:
        await self._send(payload)

    async def set_power(self, on: bool) -> None:
        await self._send(protocol.power(on, self.dialect))

    async def stop_effect(self) -> None:
        """Stop an onboard effect / return to a static colour."""
        await self._send(protocol.static_mode())

    async def set_color(self, r: int, g: int, b: int) -> None:
        await self._send(protocol.color(r, g, b, self.dialect))

    async def set_color_hex(self, text: str) -> None:
        await self.set_color(*rgb_from_text(text))

    async def set_brightness(self, percent: int) -> None:
        percent = protocol.clamp(percent, 0, 100)
        if self.dialect is Dialect.LEGACY:
            native = percent
        else:
            native = round(percent * 255 / 100)
        await self._send(protocol.brightness(native, self.dialect))

    async def set_effect(self, name_or_code: str | int) -> int:
        code = self.resolve_effect(name_or_code)
        await self._send(protocol.effect(code, self.dialect))
        return code

    async def set_effect_speed(self, percent: int) -> None:
        percent = protocol.clamp(percent, 0, 100)
        if self.dialect is Dialect.LEGACY:
            native = percent
        else:
            native = round(percent * 255 / 100)
        await self._send(protocol.effect_speed(native, self.dialect))

    async def set_color_temp(self, warm: int, cold: int) -> None:
        await self._send(protocol.color_temp(warm, cold, self.dialect))

    async def set_preset(self, index: int) -> None:
        await self._send(protocol.preset(index, self.dialect))

    async def set_mic(self, on: bool) -> None:
        await self._send(protocol.mic(on, self.dialect))

    async def set_mic_sensitivity(self, percent: int) -> None:
        value = round(protocol.clamp(percent, 0, 100) * 255 / 100)
        await self._send(protocol.mic_sensitivity(value, self.dialect))

    async def set_mic_eq(self, code: int) -> None:
        await self._send(protocol.mic_eq(code, self.dialect))

    async def sync_time(self, when: Any = None) -> None:
        import datetime

        when = when or datetime.datetime.now()
        await self._send(
            protocol.sync_time(
                when.hour, when.minute, when.second, when.isoweekday()
            )
        )

    def resolve_effect(self, name_or_code: str | int) -> int:
        table = protocol.effects(self.dialect)
        if isinstance(name_or_code, str):
            key = name_or_code.strip().lower().replace("-", "_").replace(" ", "_")
            if key in table:
                return table[key]
            if key.isdigit():
                return int(key)
            raise ValueError(
                f"unknown effect {name_or_code!r}; choose from: {', '.join(table)}"
            )
        return int(name_or_code)

    async def info(self) -> dict[str, Any]:
        await self.ensure_connected()
        assert self._client is not None
        services = []
        for service in self._client.services:
            chars = []
            for char in service.characteristics:
                chars.append(
                    {
                        "uuid": char.uuid,
                        "handle": char.handle,
                        "properties": sorted(char.properties),
                    }
                )
            services.append({"uuid": service.uuid, "characteristics": chars})
        return {
            "address": self._client.address,
            "name": getattr(self._client, "name", None) or self.address,
            "mtu": getattr(self._client, "_mtu_size", None) or 23,
            "services": services,
        }

    async def read_info(self) -> bytes:
        """Read the controller's info characteristic (FFF4)."""
        await self.ensure_connected()
        assert self._client is not None
        return bytes(
            await self._client.read_gatt_char(protocol.NOTIFY_CHARACTERISTIC_UUID)
        )

    async def animate(
        self,
        name: str = "rainbow",
        duration: float = 10.0,
        fps: float = 50.0,
        color: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        """PC-driven animation using the verified colour command.

        The controller's own effect commands are not reliable on this
        firmware, so animations are streamed from the PC instead.
        """
        name = name.strip().lower()
        if name not in {"rainbow", "strobe", "breathe", "cycle"}:
            raise ValueError(
                "animation must be one of: rainbow, strobe, breathe, cycle"
            )
        fps = max(0.5, min(20.0, float(fps)))
        palette = [
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
            (0, 255, 255),
            (255, 0, 255),
            (255, 255, 255),
        ]
        loop = asyncio.get_running_loop()
        start = loop.time()
        while True:
            elapsed = loop.time() - start
            if elapsed >= duration:
                break
            if name == "rainbow":
                r, g, b = colorsys.hsv_to_rgb((elapsed * 0.15) % 1.0, 1.0, 1.0)
                rgb = (round(r * 255), round(g * 255), round(b * 255))
            elif name == "strobe":
                rgb = color if int(elapsed * 4) % 2 == 0 else (0, 0, 0)
            elif name == "breathe":
                level = 0.15 + 0.85 * (
                    0.5 + 0.5 * math.sin(elapsed * math.tau * 0.5)
                )
                rgb = tuple(round(c * level) for c in color)
            else:  # cycle
                rgb = palette[int(elapsed * 2) % len(palette)]
            await self._send(protocol.color(*rgb, self.dialect), delay=0)
            await asyncio.sleep(1.0 / fps)

    async def test_sequence(self) -> None:
        """Visible smoke test: red, green, blue, white, rainbow, brightness."""
        steps: list[tuple[str, Any]] = [
            ("power on", lambda: self.set_power(True)),
            ("red", lambda: self.set_color(255, 0, 0)),
            ("green", lambda: self.set_color(0, 255, 0)),
            ("blue", lambda: self.set_color(0, 0, 255)),
            ("white", lambda: self.set_color(255, 255, 255)),
            (
                "rainbow animation (2.5s)",
                lambda: self.animate("rainbow", duration=2.5, fps=20),
            ),
            ("brightness 30%", lambda: self.set_brightness(30)),
            ("brightness 100%", lambda: self.set_brightness(100)),
            ("power off", lambda: self.set_power(False)),
            ("power on", lambda: self.set_power(True)),
            ("white", lambda: self.set_color(255, 255, 255)),
        ]
        for label, action in steps:
            print(f"-- {label}")
            await action()
            await asyncio.sleep(1.2)
