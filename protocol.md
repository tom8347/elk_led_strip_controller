# ELK-BLEDDM protocol notes

Verified against a strip advertising as `ELK-BLEDDM`. The USB connection is
power-only.

## GATT

| Item | Value |
|---|---|
| Service | `0000fff0-0000-1000-8000-00805f9b34fb` |
| Write characteristic | `0000fff3-0000-1000-8000-00805f9b34fb` |
| Properties | `read`, `write`, `write-without-response` |
| Notify/info characteristic | `0000fff4-0000-1000-8000-00805f9b34fb` |
| Properties | `read`, `notify` |
| Info blob | firmware/model string, unit-specific |
| Negotiated MTU | 23 (default; 9-byte frames fit easily) |

No pairing/bonding needed. Writes are sent with `response=False` and a
**300 ms** settle time between commands. The BLEDDM silently drops commands
sent closer together (for example an effect immediately followed by its
speed). One BLE central at a time.

## Framing

All commands are 9 bytes:

```
7E  LEN  CMD  A  B  C  D  E  EF
```

`LEN` is a length/format byte rather than a strict payload count. The
`modern` dialect is what the Lotus Lantern app (`com.easylink.colorful`,
package `wl.smartled`) sends to this ELK-BLEDDM unit.

## Modern dialect (static controls verified)

| Action | Packet |
|---|---|
| Power on | `7E 04 04 01 00 01 FF 00 EF` |
| Power off | `7E 04 04 00 00 00 FF 00 EF` |
| RGB colour | `7E 07 05 03 RR GG BB 10 EF` |
| Brightness (native 0-255) | `7E 04 01 BB FF FF FF 00 EF` |
| Effect (code 0-21) | `7E 05 03 (code\|0x80) 03 FF FF 00 EF` |
| Effect speed (native 0-255) | `7E 04 02 SS FF FF FF 00 EF` |
| Warm/cold white | `7E 06 05 02 WW CC FF 08 EF` |
| Preset colour index | `7E 05 05 01 II FF FF 08 EF` |
| Mic on/off | `7E 04 07 01/00 FF FF FF 00 EF` |
| Mic sensitivity | `7E 04 06 SS FF FF FF 00 EF` |
| Mic EQ/mode | `7E 05 03 (code\|0x80) 04 FF FF 00 EF` |
| Pin sequence | `7E 06 81 RR GG BB FF 00 EF` |
| Stop effect / static mode | `7E 00 05 01 00 00 00 00 EF` |

The CLI maps `brightness 0-100` and `speed 0-100` to `0-255` for this
dialect. `temp WARM COLD` takes native `0-255` values.

### Modern effect codes

| Code | Name |
|---|---|
| `00` | `jump_rgb` |
| `01` | `jump_seven` |
| `02` | `crossfade_rgb` |
| `03` | `crossfade_seven` |
| `04`-`0A` | `crossfade_red`, `_green`, `_blue`, `_yellow`, `_cyan`, `_magenta`, `_white` |
| `0B`-`0D` | `crossfade_red_green`, `_red_blue`, `_green_blue` |
| `0E`-`14` | `strobe_red`, `_green`, `_blue`, `_yellow`, `_cyan`, `_magenta`, `_white` |
| `15` | `strobe_seven` |

`elk effects` prints the authoritative table. Colour, brightness, white
balance, presets and mic were visually confirmed on this unit. The onboard
effect packets were sent but did not produce a reliable animation — see below.

### Onboard effects: not reliable on this firmware

Neither the modern effect frame (`7E 05 03 …`), the legacy frame
(`7E 00 03 …`), the BLEDOM0E frame (`7E 07 03 …`) nor the MELK frame
(`7E 05 03 … 06 …`) produced continuous animation when tested in isolation.
Observed results were a brief colour change followed by a static colour, or
nothing. This looks like a firmware variant that either ignores the onboard
effect commands or expects a different sequence.

The `7E 00 05 01 …` packet reliably stops any effect that is running, but it
also appears to lock out new effects until a power cycle.

The reliable approach is to stream colour updates from the PC:
`elk animate rainbow|strobe|breathe|cycle`. 50 FPS is the practical ceiling
over this BLE link; 20-50 FPS both work.

## Legacy dialect (implemented, not verified on this unit)

Original ELK-BLEDOM framing uses `LEN=00` and different effect bytes:

| Action | Packet |
|---|---|
| Power on | `7E 00 04 F0 00 01 FF 00 EF` |
| Power off | `7E 00 04 00 00 00 FF 00 EF` |
| RGB colour | `7E 00 05 03 RR GG BB 00 EF` |
| Brightness (0-100) | `7E 00 01 BB 00 00 00 00 EF` |
| Effect (raw code) | `7E 00 03 CC 03 00 00 00 EF` |
| Effect speed (0-100) | `7E 00 02 SS 00 00 00 00 EF` |
| Warm/cold white | `7E 00 05 02 WW CC 00 00 EF` |
| Preset colour index | `7E 00 05 01 II 00 00 00 EF` |
| Clock sync | `7E 00 83 HH MM SS DOW 00 EF` |

Legacy effect codes are the `0x87`-`0x9C` range (`jump_rgb=0x87`,
`jump_seven=0x88`, `crossfade_rgb=0x89`, ... `strobe_seven=0x95`). Use
`--dialect legacy`; `sync-time` is only meaningful there. The legacy effect
frame was also tested on this unit and did not animate reliably.

## Model database reference

The most complete public table of these variants is
[dave-code-ruiz/elkbledom](https://github.com/dave-code-ruiz/elkbledom),
especially `custom_components/elkbledom/models.json` and
`definitions.json`. Its `ELK-BLEDDM` entry uses a mix of frames:

```
turn_on      7E 04 04 F0 00 01 FF 00 EF
turn_off     7E 04 04 00 00 00 FF 00 EF
color        7E 00 05 03 RR GG BB 00 EF
brightness   7E 04 01 BB FF 00 FF 00 EF
effect       7E 00 03 CC 03 00 00 00 EF
effect_speed 7E 00 02 SS 00 00 00 00 EF
color_temp   7E 00 05 02 WW CC 00 00 EF
white        7E 00 01 BB 00 00 00 00 EF
```

This is why a single "modern vs legacy" dialect flag is only an
approximation. The working static controls here use the modern frames, which
the unit accepts.

## How this was derived

1. Identified the device with a BLE scan (`ELK-BLEDDM`); `lsusb` showed no
   USB LED device, confirming BLE-only control.
2. The family is public: the Lotus Lantern app's `BluetoothLEService.java`
   contains the byte layout, and the packet builders here match
   [Tech-Morph/Lotus-Lantern-HA](https://github.com/Tech-Morph/Lotus-Lantern-HA).
   Other useful references:
   [TheSylex/ELK-BLEDOM](https://github.com/TheSylex/ELK-BLEDOM-bluetooth-led-strip-controller),
   [FergusInLondon/ELK-BLEDOM](https://github.com/FergusInLondon/ELK-BLEDOM),
   [abduoqb/LED-BLEDDM-CONTROL](https://github.com/abduoqb/LED-BLEDDM-CONTROL).
3. GATT discovery confirmed the `FFF0` service and `FFF3` write
   characteristic.
4. A packet-level smoke test plus visual confirmation established the modern
   static controls and brightness scaling. Onboard effects were then tested
   against all four known frame layouts; none produced a reliable animation,
   so animations are PC-driven.
5. All packet builders have byte-exact unit tests in
   `tests/test_protocol.py`.

## If you need to capture traffic

For a future/unknown variant:

```bash
# Linux, while driving the strip with the CLI
sudo btmon -w captures/strip.btsnoop
tshark -r captures/strip.btsnoop -Y 'btatt.opcode == 0x52' -T fields \
  -e btatt.handle -e btatt.value
```

Android: enable Developer options -> "Enable Bluetooth HCI snoop log", drive
the app, then `adb pull /sdcard/btsnoop_hci.log` (or
`/data/misc/bluetooth/logs/`). Group ATT writes by handle and diff packets
per button press.

For APK work, the relevant app is `com.easylink.colorful`; `jadx` plus a grep
for the `FFF3` UUID / `writeCharacteristic` is usually enough. Agent-side
tooling such as [REA](https://github.com/morluto/rea) or GhidraMCP is useful
for obfuscated apps or firmware, but was not needed here.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for protocol references
and licenses.
