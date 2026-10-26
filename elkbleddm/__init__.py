"""PC-side control for ELK-BLEDDM / ELK-BLEDOM Bluetooth LED strips."""

from .controller import ELKStrip
from .protocol import (
    Dialect,
    SERVICE_UUID,
    WRITE_CHARACTERISTIC_UUID,
    NOTIFY_CHARACTERISTIC_UUID,
)

__all__ = [
    "ELKStrip",
    "Dialect",
    "SERVICE_UUID",
    "WRITE_CHARACTERISTIC_UUID",
    "NOTIFY_CHARACTERISTIC_UUID",
]
