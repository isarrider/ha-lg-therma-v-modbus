"""Compressor starts, run time, average speed and defrosts, from polled data.

Counted from the Compressor (10004) and Defrost (10005) discrete inputs and
Compressor Speed (input 30025) on every poll; nothing extra is read from the
unit. With the Compressor statistics option, five sensors show them:

- Compressor Starts: off-to-on changes, a total counter (starts per day or
  per hour come from Home Assistant's statistics). Many short runs mean the
  unit is cycling, which costs efficiency and wear.
- Compressor Run Time: hours the compressor ran, a total counter.
- Compressor Average Speed: rpm while running, today (reset at local
  midnight), so it can be compared day by day. Standstill is left out, or the
  value would measure how often it runs, not how hard.
- Defrosts: off-to-on changes of the Defrost input, a total counter.
- Defrost Time: minutes spent defrosting, a total counter.
- Defrost Energy: the heat the defrosts take out of the heating water, kWh,
  a total counter. From the calculated thermal power (flow × ΔT, negative
  while the water loses heat): added up while the unit defrosts and after it,
  until the thermal power is no longer negative, as the water flowing through
  the cold heat exchanger keeps losing heat for a moment. Negative values
  outside a defrost (sensor noise at standstill) are not counted.

Starts and defrosts also count today (reset at local midnight, kept across
restarts), shown as an attribute, so a dashboard can show today and the total
side by side without asking the statistics.

Every poll counts the state seen at the previous poll over the time since
(left Riemann sum), like the energy integration in external_meter.py. The
interval that crosses midnight counts to the new day (at most one poll
interval). A gap
longer than MAX_GAP_S is not counted, and a start is only counted between two
polls that are both known, so a restart never adds one.

Deliberately free of Home Assistant imports so it can be tested without a
Home Assistant install, like energy.py.
"""

from __future__ import annotations

from typing import Any

# Entity keys (docs/naming.md).
KEY_COMPRESSOR_STARTS = "compressor_starts"
KEY_COMPRESSOR_RUN_TIME = "compressor_run_time"
KEY_COMPRESSOR_AVERAGE_SPEED = "compressor_average_speed"
KEY_DEFROSTS = "defrosts"
KEY_DEFROST_TIME = "defrost_time"
KEY_DEFROST_ENERGY = "defrost_energy"
KEYS = (
    KEY_COMPRESSOR_STARTS,
    KEY_COMPRESSOR_RUN_TIME,
    KEY_COMPRESSOR_AVERAGE_SPEED,
    KEY_DEFROSTS,
    KEY_DEFROST_TIME,
    KEY_DEFROST_ENERGY,
)

MAX_GAP_S = 300.0


class CompressorStats:
    """The running counts, fed one poll at a time."""

    def __init__(self) -> None:
        self.starts = 0
        self.run_s = 0.0
        self.defrosts = 0
        self.defrost_s = 0.0
        # Heat taken out of the water by defrosts, in watt-seconds.
        self.defrost_ws = 0.0
        # Today: the day, seconds running, rpm × s, starts, defrosts and
        # seconds defrosting.
        self.day: str | None = None
        self.day_run_s = 0.0
        self.day_rpm_s = 0.0
        self.day_starts = 0
        self.day_defrosts = 0
        self.day_defrost_s = 0.0
        self.day_defrost_ws = 0.0
        # The run in progress, or the last one: its duration in seconds.
        self.last_run_s: float | None = None
        self._on: bool | None = None
        self._rpm: float | None = None
        self._time_s: float | None = None
        self._run_started_s: float | None = None
        # The defrost in progress, or the last one: its duration in seconds.
        self.last_defrost_s: float | None = None
        self._defrost: bool | None = None
        self._defrost_time_s: float | None = None
        self._defrost_started_s: float | None = None
        # Thermal power at the previous poll, and whether its heat loss is
        # counted: during a defrost and after it while still negative.
        self._thermal_w: float | None = None
        self._defrost_tail = False

    def add(
        self,
        on: bool | None,
        rpm: float | None,
        time_s: float,
        day: str,
        defrost: bool | None = None,
        thermal_w: float | None = None,
    ) -> None:
        """Record one poll: compressor on/off (None: unknown), speed, time, day,
        defrosting (None: unknown), calculated thermal power in W (None:
        unknown)."""
        if day != self.day:
            self.day = day
            self.day_run_s = 0.0
            self.day_rpm_s = 0.0
            self.day_starts = 0
            self.day_defrosts = 0
            self.day_defrost_s = 0.0
            self.day_defrost_ws = 0.0
        self._add_defrost(defrost, time_s, thermal_w)
        elapsed = (
            time_s - self._time_s
            if self._time_s is not None and self._on is not None
            else None
        )
        if elapsed is not None and 0 < elapsed <= MAX_GAP_S:
            if self._on:
                self.run_s += elapsed
                self.day_run_s += elapsed
                if self._rpm is not None:
                    self.day_rpm_s += self._rpm * elapsed
            if on and not self._on:
                self.starts += 1
                self.day_starts += 1
                self._run_started_s = time_s
        # The run in progress grows with every poll; a stop fixes its length.
        if self._run_started_s is not None and (on or self._on):
            self.last_run_s = time_s - self._run_started_s
        if not on:
            self._run_started_s = None
        self._on = on
        self._rpm = rpm if on else None
        self._time_s = time_s

    def _add_defrost(
        self, defrost: bool | None, time_s: float, thermal_w: float | None
    ) -> None:
        """The same counting as for the compressor, for the Defrost input;
        and the heat the water loses during and right after a defrost."""
        elapsed = (
            time_s - self._defrost_time_s
            if self._defrost_time_s is not None and self._defrost is not None
            else None
        )
        if elapsed is not None and 0 < elapsed <= MAX_GAP_S:
            counted = self._defrost or self._defrost_tail
            if counted and self._thermal_w is not None and self._thermal_w < 0:
                self.defrost_ws -= self._thermal_w * elapsed
                self.day_defrost_ws -= self._thermal_w * elapsed
            if self._defrost:
                self.defrost_s += elapsed
                self.day_defrost_s += elapsed
            if defrost and not self._defrost:
                self.defrosts += 1
                self.day_defrosts += 1
                self._defrost_started_s = time_s
        if self._defrost_started_s is not None and (defrost or self._defrost):
            self.last_defrost_s = time_s - self._defrost_started_s
        if not defrost:
            self._defrost_started_s = None
        # After a defrost, keep counting while the water still loses heat.
        if defrost:
            self._defrost_tail = False
        elif self._defrost:
            self._defrost_tail = True
        if self._defrost_tail and (thermal_w is None or thermal_w >= 0):
            self._defrost_tail = False
        self._defrost = defrost
        self._defrost_time_s = time_s
        self._thermal_w = thermal_w

    @property
    def run_hours(self) -> float:
        return self.run_s / 3600

    @property
    def defrost_minutes(self) -> float:
        return self.defrost_s / 60

    @property
    def defrost_kwh(self) -> float:
        return self.defrost_ws / 3_600_000

    @property
    def day_defrost_kwh(self) -> float:
        return self.day_defrost_ws / 3_600_000

    @property
    def average_rpm_today(self) -> int | None:
        """Average speed while running today, or None before the first run."""
        if self.day_run_s <= 0:
            return None
        return int(round(self.day_rpm_s / self.day_run_s))

    def restore(self, data: dict[str, Any]) -> None:
        """Continue from what a previous run stored (see state())."""
        # Stored before 2.2.9 without the defrost and per-day counts: 0.
        self.starts = int(data.get("starts") or 0)
        self.run_s = float(data.get("run_s") or 0.0)
        self.defrosts = int(data.get("defrosts") or 0)
        self.defrost_s = float(data.get("defrost_s") or 0.0)
        # Stored before 2.3.0 without the defrost energy: 0.
        self.defrost_ws = float(data.get("defrost_ws") or 0.0)
        if data.get("day") is not None and self.day in (None, data["day"]):
            self.day = data["day"]
            self.day_run_s += float(data.get("day_run_s") or 0.0)
            self.day_rpm_s += float(data.get("day_rpm_s") or 0.0)
            self.day_starts += int(data.get("day_starts") or 0)
            self.day_defrosts += int(data.get("day_defrosts") or 0)
            self.day_defrost_s += float(data.get("day_defrost_s") or 0.0)
            self.day_defrost_ws += float(data.get("day_defrost_ws") or 0.0)
        self.last_run_s = data.get("last_run_s")
        self.last_defrost_s = data.get("last_defrost_s")

    def state(self) -> dict[str, Any]:
        return {
            "starts": self.starts,
            "run_s": self.run_s,
            "day": self.day,
            "day_run_s": self.day_run_s,
            "day_rpm_s": self.day_rpm_s,
            "last_run_s": self.last_run_s,
            "defrosts": self.defrosts,
            "defrost_s": self.defrost_s,
            "day_starts": self.day_starts,
            "day_defrosts": self.day_defrosts,
            "day_defrost_s": self.day_defrost_s,
            "last_defrost_s": self.last_defrost_s,
            "defrost_ws": self.defrost_ws,
            "day_defrost_ws": self.day_defrost_ws,
        }
