# ELK-BLEDDM LED strip controller

PC-side Bluetooth LE control for LED strips that advertise as
**`ELK-BLEDDM`** (or the compatible `ELK-BLEDOM` family). The USB cable only
supplies power; all control is BLE.

Verified against the real strip: power, RGB colour, brightness, white
balance, presets, the onboard microphone/music mode, PC-driven animation, and
Ambilight-style screen sync. Onboard effect commands are implemented but this
firmware does not run them reliably, so effects are streamed from the PC
instead (`elk animate ...`).

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
elk screen --fps 60
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
| `elk screen [--fps 60] [--mode edge]` | sync the strip to the screen |
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

## Screen sync (ambilight)

```bash
elk screen --fps 60                 # until Ctrl+C
elk screen --duration 60 --mode edge
elk screen --region focused --fps 60
```

The strip is single-zone (all LEDs show the same colour), so screen sync
reduces the screen to one RGB value:

| Option | Description |
|---|---|
| `--mode average` | average the whole screen (default) |
| `--mode edge` | average the outer 25% bands, TV-ambilight style |
| `--mode dominant` | prefer saturated/bright pixels |
| `--region full\|focused` | whole output, or focused window at startup |
| `--fps 1-120` | capture/update rate (default 60) |
| `--smoothing 0-1` | 0 = instant, 1 = maximum smoothing |
| `--saturation` | colour boost (default 1.3) |
| `--gain` | RGB scaling (default 1.0) |
| `--min-change` | skip tiny updates (default 4) |
| `--power-every N` | re-send power-on every N s, so a strip switched off at the remote comes back (default 0 = never) |
| `--geometry 'x,y WxH'` | explicit capture region |
| `--stats` | print frames, sends and FPS |

Performance measured on the test machine: `wf-recorder` sustained 29 / 58 /
117 FPS at 64×36; the BLE link accepts ~880 colour writes/s, so the strip is
not the bottleneck. The monitor refreshes at 74.8 Hz, so 60 FPS is the
default and 75 FPS matches the display; above ~75 FPS the extra frames are
duplicates. At 60 FPS the update looked smooth with no significant delay.

`wf-recorder` is bundled into the packaged `elk` wrapper. `--region focused`
also needs `hyprctl` from the running Hyprland session. Protected/DRM video
may capture as black. Use `--mode edge` if the strip is mounted around the
monitor; `--mode average` suits a strip behind the screen.

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
elkbleddm/screen.py     wf-recorder screen capture + colour extraction
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

- systemd user service for automatic screen sync / schedules (the controller
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
