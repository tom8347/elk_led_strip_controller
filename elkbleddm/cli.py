#!/usr/bin/env python3
"""CLI for an ELK-BLEDDM / ELK-BLEDOM Bluetooth LED strip."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from elkbleddm import ELKStrip
from elkbleddm import protocol
from elkbleddm.protocol import Dialect


def parse_color(values: list[str]) -> tuple[int, int, int]:
    if len(values) == 1:
        return _hex(values[0])
    if len(values) == 3:
        return int(values[0]), int(values[1]), int(values[2])
    raise SystemExit("color expects '#rrggbb' or three numbers: R G B")


def _hex(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise SystemExit("colour must look like #rrggbb")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="elk.py",
        description="Control an ELK-BLEDDM / ELK-BLEDOM BLE LED strip.",
    )
    parser.add_argument(
        "--address",
        default=os.environ.get("ELK_ADDRESS"),
        help="BLE address (default: auto-discover by name)",
    )
    parser.add_argument(
        "--name",
        dest="name_prefix",
        default=os.environ.get("ELK_NAME", "ELK-BLEDDM"),
        help="advertised name prefix for auto-discovery",
    )
    parser.add_argument(
        "--dialect",
        choices=[d.value for d in Dialect],
        default=os.environ.get("ELK_DIALECT", Dialect.MODERN.value),
        help="protocol variant (default: modern)",
    )
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="settle time between commands (BLEDDM needs ~0.3s)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("scan", help="scan for nearby BLE devices")
    sub.add_parser("info", help="connect and dump GATT services/characteristics")
    sub.add_parser("device-info", help="read the controller's version/info blob (FFF4)")
    sub.add_parser("on", help="turn the strip on")
    sub.add_parser("off", help="turn the strip off")
    sub.add_parser("test", help="visible smoke test: colours, animation, brightness")
    sub.add_parser("stop-effect", help="stop an onboard effect / return to static")
    sub.add_parser("effects", help="list effect names for the selected dialect")
    sub.add_parser("sync-time", help="set the controller clock (legacy dialect)")

    p = sub.add_parser("animate", help="PC-driven animation")
    p.add_argument("animation", choices=["rainbow", "strobe", "breathe", "cycle"])
    p.add_argument("--duration", type=float, default=10.0)
    p.add_argument("--fps", type=float, default=50.0)
    p.add_argument("--color", default="#ffffff", help="base colour for strobe/breathe")

    p = sub.add_parser("color", help="set RGB colour")
    p.add_argument("value", nargs="+", help="#rrggbb or R G B")

    p = sub.add_parser("brightness", help="set brightness, 0-100 percent")
    p.add_argument("percent", type=int)

    p = sub.add_parser("effect", help="select an effect by name or code")
    p.add_argument("name")

    p = sub.add_parser("speed", help="set effect speed, 0-100 percent")
    p.add_argument("percent", type=int)

    p = sub.add_parser("temp", help="set warm/cold white balance, 0-255 each")
    p.add_argument("warm", type=int)
    p.add_argument("cold", type=int)

    p = sub.add_parser("preset", help="select a preset colour index")
    p.add_argument("index", type=int)

    p = sub.add_parser("mic", help="toggle the onboard microphone (modern only)")
    p.add_argument("state", choices=["on", "off"])

    p = sub.add_parser("mic-sensitivity", help="mic sensitivity, 0-100 percent")
    p.add_argument("percent", type=int)

    p = sub.add_parser("eq", help="mic equaliser/mode code (modern only)")
    p.add_argument("code", type=int)

    p = sub.add_parser("raw", help="send an arbitrary hex packet")
    p.add_argument("payload")

    return parser


def make_strip(args: argparse.Namespace) -> ELKStrip:
    return ELKStrip(
        address=args.address,
        name_prefix=args.name_prefix,
        dialect=args.dialect,
        timeout=args.timeout,
        command_delay=args.delay,
        verbose=args.verbose,
    )


async def run(args: argparse.Namespace) -> None:
    if args.cmd == "scan":
        devices = await ELKStrip.discover(args.timeout)
        for device in devices:
            rssi = getattr(device, "rssi", "?")
            print(f"{device.address}  {rssi:>4}  {device.name}")
        return

    if args.cmd == "effects":
        table = protocol.effects(args.dialect)
        for name, code in table.items():
            print(f"{code:#04x}  {name}")
        return

    strip = make_strip(args)

    if args.cmd == "test":
        async with strip:
            await strip.test_sequence()
        return

    async with strip:
        if args.cmd == "info":
            print(json.dumps(await strip.info(), indent=2))
        elif args.cmd == "device-info":
            data = await strip.read_info()
            printable = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
            print(f"hex:   {data.hex(' ')}")
            print(f"ascii: {printable}")
        elif args.cmd == "stop-effect":
            await strip.stop_effect()
            print("effect stopped")
        elif args.cmd == "animate":
            await strip.animate(
                args.animation,
                duration=args.duration,
                fps=args.fps,
                color=_hex(args.color),
            )
            print(f"animation {args.animation} finished")
        elif args.cmd == "on":
            await strip.set_power(True)
            print("on")
        elif args.cmd == "off":
            await strip.set_power(False)
            print("off")
        elif args.cmd == "color":
            await strip.set_color(*parse_color(args.value))
            print("color set")
        elif args.cmd == "brightness":
            await strip.set_brightness(args.percent)
            print(f"brightness {args.percent}%")
        elif args.cmd == "effect":
            code = await strip.set_effect(args.name)
            print(f"effect {args.name} ({code:#04x})")
        elif args.cmd == "speed":
            await strip.set_effect_speed(args.percent)
            print(f"speed {args.percent}%")
        elif args.cmd == "temp":
            await strip.set_color_temp(args.warm, args.cold)
            print(f"temp warm={args.warm} cold={args.cold}")
        elif args.cmd == "preset":
            await strip.set_preset(args.index)
            print(f"preset {args.index}")
        elif args.cmd == "mic":
            await strip.set_mic(args.state == "on")
            print(f"mic {args.state}")
        elif args.cmd == "mic-sensitivity":
            await strip.set_mic_sensitivity(args.percent)
            print(f"mic sensitivity {args.percent}%")
        elif args.cmd == "eq":
            await strip.set_mic_eq(args.code)
            print(f"mic eq {args.code}")
        elif args.cmd == "raw":
            await strip.send_raw(protocol.from_hex(args.payload))
            print("raw packet sent")
        elif args.cmd == "sync-time":
            await strip.sync_time()
            print("time synced")
        else:
            raise SystemExit(f"unknown command {args.cmd}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        if args.verbose:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
