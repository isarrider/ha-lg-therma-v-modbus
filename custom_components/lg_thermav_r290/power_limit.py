"""Active power limitation (holding register 24 + coil 6). UNVERIFIED.

Holding 24 (40025) is said to hold a maximum electrical power in tenths of a
kW (0.1-25.0 kW), and coil 6 (00007) to switch that limitation on and off.
Neither is in the manual's table, and the only source is a community forum.
Nobody has confirmed that writing them has any effect on an R290: the 9 kW
unit in docs/register-scan.md does not even answer on either address, and it
is untested on a 12 kW unit.

The integration therefore reads and writes them only while the option asks
for it, and the coordinator adds them to its write whitelist only then.
Every power value is clamped to 0.1-25.0 kW before it reaches the bus.

Deliberately free of Home Assistant imports so the encoding can be tested
without a Home Assistant install, like limits.py.
"""

from __future__ import annotations

POWER_LIMIT_REGISTER = 24  # holding, 0-based (40025)
POWER_LIMIT_COIL = 6  # coil, 0-based (00007)

POWER_LIMIT_MIN_KW = 0.1
POWER_LIMIT_MAX_KW = 25.0
_RAW_MIN = 1  # 0.1 kW in tenths
_RAW_MAX = 250  # 25.0 kW in tenths

# Coordinator data keys.
DATA_KEY_KW = "power_limit_kw"  # limit in kW, None while the register reads 0
DATA_KEY_RAW = "power_limit_raw"  # holding 24 as read
DATA_KEY_ACTIVE = "power_limit_active"  # coil 6 as read

# Unique id suffixes, used to drop the entities from the entity registry when
# the option is switched off.
NUMBER_UNIQUE_ID_SUFFIX = "power_limit"
SWITCH_UNIQUE_ID_SUFFIX = "power_limit_active"


def decode(raw: int, active: bool) -> dict[str, float | int | bool | None]:
    """Coordinator data for one read of holding 24 and coil 6.

    A raw 0 has no place on a 0.1-25.0 kW slider and is kept apart (kW None)
    rather than shown as a power it is not. Any other value is reported as
    read, so something unexpected shows instead of being hidden by clamping.
    """
    return {
        DATA_KEY_KW: None if raw == 0 else round(raw / 10, 1),
        DATA_KEY_RAW: raw,
        DATA_KEY_ACTIVE: bool(active),
    }


def encode(kw: float) -> int:
    """Register value (tenths of a kW) for a requested limit, clamped."""
    raw = int(round(kw * 10))
    return max(_RAW_MIN, min(_RAW_MAX, raw))
