# ELK-BLEDDM LED strip controller

PC-side Bluetooth LE control for LED strips that advertise as
**`ELK-BLEDDM`** (or the compatible `ELK-BLEDOM` family). The USB cable only
supplies power; all control is BLE.

Verified against the real strip: power, RGB colour, brightness, white
balance, presets and the onboard microphone/music mode. Onboard effect
commands are implemented but this firmware does not run them reliably, so
effects are streamed from the PC instead (`elk animate ...`), which works at
50 FPS.

## Quick start

```bash
direnv allow          # first time only
python elk.py test    # visible smoke test
```

Without the dev shell, the packaged flake works directly:

```bash
nix run . -- test
nix run . -- color '#ff6600'
nix profile install .   # installs `elk` into the profile
```

Or, once the dev shell is active, the `elk` wrapper is on `PATH`:

```bash
elk on
elk color '#ff6600'
elk brightness 40
elk animate rainbow --duration 15
elk off
```

## Commands

| Command | Description |
|---|---|
| `elk scan` | list nearby BLE devices |
| `elk info` | connect and dump GATT services/characteristics |
| `elk device-info` | read the controller version/info blob |
| `elk on` / `elk off` | power |
| `elk color '#rrggbb'` or `elk color R G B` | static RGB colour |
| `elk brightness 0-100` | brightness |
| `elk animate rainbow\|strobe\|breathe\|cycle` | PC-driven animation |
| `elk animate ... --duration 30 --fps 50` | animation length/rate |
| `elk animate ... --color '#ff6600'` | base colour for `strobe`/`breathe` |
| `elk stop-effect` | stop an onboard effect / return to static |
| `elk effect NAME\|CODE` | onboard effect (unreliable on this firmware) |
| `elk speed 0-100` | onboard effect speed (same caveat) |
| `elk temp WARM COLD` | warm/cold white balance, each `0-255` |
| `elk preset 0-255` | preset colour index |
| `elk mic on\|off` | onboard microphone/music mode |
| `elk mic-sensitivity 0-100` | mic sensitivity |
| `elk eq CODE` | mic equaliser/mode (`0-7` observed) |
| `elk raw '7e ... ef'` | send an arbitrary 9-byte packet |
| `elk test` | visible sequence: colours, animation, brightness, power |
| `elk sync-time` | legacy clock sync (not needed for modern units) |

Global options:

```bash
--address <strip-address>     # skip discovery
--name ELK-BLEDDM             # discovery prefix
--dialect modern|legacy       # default modern; legacy for original ELK-BLEDOM
--timeout 8
--delay 0.3                   # BLEDDM drops commands sent <300ms apart
-v                            # print every packet sent
```

Environment variables `ELK_ADDRESS`, `ELK_NAME` and `ELK_DIALECT` are also
honoured.

## Troubleshooting

- **Only one BLE central at a time.** Force-stop the phone app or turn off
  the phone's Bluetooth before connecting from the PC. A failed connect
  while the phone is attached is the usual cause.
- **`no BLE device matching ...`** — strip unpowered/out of range, or still
  connected to the phone. `elk scan` will show what is visible.
- **Modern dialect does nothing** — try `--dialect legacy`. Only the modern
  dialect was verified on this exact unit.
- **Onboard effects don't animate** — expected on this firmware. Use
  `elk animate ...`; the colour command is reliable.
- **Commands are ignored when sent quickly** — keep the default
  `--delay 0.3`. The BLEDDM drops packets sent closer together.
- **USB is power only.** `lsusb` shows no LED device; do not look for a USB
  protocol.

## Layout

```
elkbleddm/cli.py        argparse CLI (installed as `elk`)
elkbleddm/protocol.py   packet builders for both dialects
elkbleddm/controller.py async BLE connection + high-level controls
elk.py                  compatibility shim for `python elk.py`
tests/test_protocol.py  byte-exact packet tests
protocol.md             full protocol reference and reverse-engineering notes
pyproject.toml          Python package + console script metadata
flake.nix / .envrc      package, app, checks and dev shell
```

The flake exposes `packages.default` / `apps.default` (so `nix run . -- ...`
works) and a `checks.default` that builds the package and runs the packet
tests (`nix flake check`).

## Next steps

- systemd user service or timer for on/off schedules (the controller already
  keeps one connection and can be imported as `elkbleddm.ELKStrip`).
- A small local HTTP/WebSocket API or GUI on top of `ELKStrip`.
- If onboard effects matter, capture the Lotus Lantern app's HCI log and send
  the exact effect packet; `protocol.md` explains the capture steps.
- More animation presets (music-reactive, chase, etc.) on top of `animate`.

## License

MIT; see [LICENSE](LICENSE). Protocol layouts were confirmed against public
reverse-engineering projects; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This project is not
affiliated with the manufacturer or the app developer.
