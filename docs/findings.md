# Findings on a 12 kW unit

What the integration's data showed about one LG Therma V R290 in daily use,
beyond what the manual says. Each finding says what was seen, how, and what
follows for the integration or for automations. Details that already have a
home elsewhere are linked rather than repeated.

**The unit:** LG Therma V R290, 12 kW, Modbus RTU (USB serial adapter), slave
ID 1, firmware kernel 3.0.9 / ramdisk 3.07.6a (2025-01-21). One heating circuit
(radiators); no backup heater, no DHW tank, no second circuit, no wired remote
controller. The house has a smart meter, so the unit's own electrical figures
can be compared with a calibrated reading.

## Contents

- [At night: fan runs and compressor preheating](#at-night-fan-runs-and-compressor-preheating)
- [The outdoor temperature reads high while the compressor is off](#the-outdoor-temperature-reads-high-while-the-compressor-is-off)
- [The evaporator coil is one sensor, reported twice](#the-evaporator-coil-is-one-sensor-reported-twice)
- [The pressures are gauge pressures](#the-pressures-are-gauge-pressures)
- [Suction is a separate sensor](#suction-is-a-separate-sensor)
- [The flow rate reads 5.0 L/min with the pump stopped](#the-flow-rate-reads-50-lmin-with-the-pump-stopped)
- [Heat goes negative during a defrost](#heat-goes-negative-during-a-defrost)
- [A cold coil is not yet ice](#a-cold-coil-is-not-yet-ice)
- [The electrical figures run high](#the-electrical-figures-run-high)
- [Heating setpoints below 20 °C are not accepted](#heating-setpoints-below-20-c-are-not-accepted)
- [Inputs without a sensor send 64887](#inputs-without-a-sensor-send-64887)
- [Room Air Temperature Circuit 1 is the plant room](#room-air-temperature-circuit-1-is-the-plant-room)
- [Cooling active is on while heating](#cooling-active-is-on-while-heating)
- [The water pump runs while Heating/Cooling is on](#the-water-pump-runs-while-heatingcooling-is-on)

COP, compressor speed and lift have their own page: [cop-efficiency.md](cop-efficiency.md).

## At night: fan runs and compressor preheating

**Seen** on 13/14 November 2026, outdoor about 1.5–4.5 °C, compressor off all
night. The house meter showed an hour of square pulses from 23:58 to 00:57,
about **180 W, split evenly over the three phases** (60 / 61 / 62 W on L1 /
L2 / L3), each about 40 seconds on and 80 seconds off; at each end a block of
about **150 W for about a minute** (41 / 70 / 37 W), at 23:55:40 and 00:57:50.
The phases come from the meter's raw values, one per second. Before and after: the standby (about 50 W by
the unit's own figure, really about 13 W, see [below](#the-electrical-figures-run-high)) and the fridge.

**The 150 W blocks are the outdoor unit's fan.** At 23:55:30 *Outdoor
Temperature* fell from 4.6 to 1.4 °C within 90 s and the evaporator coil from
7.3 to 3.1 °C; at 00:58 the same, 3.6 → 1.4 °C and 6.2 → 2.7 °C. Only moving air
does that; afterwards both crept back up. The unit runs its fan briefly to
measure the real air temperature (see the next finding). The water pump is
not part of it: it runs all the time, and its flow did not change during the
blocks ([below](#the-water-pump-runs-while-heatingcooling-is-on)).

**The pulses heat the compressor.** The unit's own *Electrical Power* read
about 300 W on the polls that hit a pulse (00:12, 00:27, 00:40, 00:45) and
46–49 W otherwise, with the compressor at 0 rpm throughout; the meter saw
about 180 W per pulse. Over the same
hour, at about 2 °C outside, *Hot Gas Temperature* rose from 15 to 20 °C (22 °C
by 01:07) and *Suction Temperature* from 13.0 to 14.7 °C. With the compressor
standing still, that heat can only come from the unit heating the compressor,
which keeps the oil warm so refrigerant does not dissolve into it before the
next start. The phases say how: the pulses load all three phases evenly, as
the compressor's inverter does, while a crankcase heater (a resistance on one
phase) would show on a single phase. So the inverter drives **current through
the motor windings** without turning the compressor. A drain pan heater would
be single-phase too, and the coil warming back up afterwards matches the still
air after the fan run.

**The sequence:** fan run → real outdoor temperature below a threshold of
roughly 2–3 °C → about an hour of preheating → fan run again. In ten days of
history such phases appeared only on nights at or below about 5 °C (as read in
still air), never on the mild nights in between.

**Cost:** about 180 W at a third of the time for an hour, about 0.06 kWh per
preheating hour; a few tenths of a kWh on a cold night at most. Normal, and it
protects the compressor.

None of the [experimental registers](register-scan.md), *Operation State ODU*
or *Operation Cycle ODU* changed during the phase, so the integration has no
register that shows it directly.

## The outdoor temperature reads high while the compressor is off

The outdoor sensor sits in the outdoor unit's still air while nothing runs, and
that air is warmer than outside: last night **about 3 K** (4.6 °C read, 1.4 °C
right after the fan run). The value is right while the compressor runs and
right after a fan run, and drifts up in between.

**For automations:** a night-time condition on *Outdoor Temperature* with the
compressor off sees 2–3 K too much. Where it matters, use a weather sensor or
the value shortly after a fan run.

## The evaporator coil is one sensor, reported twice

Inputs 30021 (*Temperature Before Evaporator*) and 30022 (*Temperature After
Evaporator*) never differed in ten days, not even by 0.1 K, at 3965 change
points including start-up, standstill and defrost. *Temperature After
Evaporator* therefore starts disabled on new installations (2.2.8). Evidence:
[register-scan.md](register-scan.md#evaporator-and-suction-sensors).

## The pressures are gauge pressures

With the compressor running, the coil reads a median 1.1 K above the boiling
temperature of propane at the low pressure, but only when the low pressure is
read as bar above atmospheric (+1 bar for absolute). Read as absolute, the
boiling coil would be about 8 K warmer than boiling propane, which is not
possible. The integration keeps the unit `bar`; Home Assistant has no gauge
unit.

## Suction is a separate sensor

Running for more than 15 minutes, suction reads a median 0.3 K (90th
percentile 3.4 K) above the coil: the superheat the expansion valve keeps
small. At standstill it is about 8 K warmer than the coil, as the suction line
warms inside the unit while the coil follows the outdoor air.

## The flow rate reads 5.0 L/min with the pump stopped

The flow sensor (SIKA VVX20, 5–80 L/min) cannot go below 5.0, so a stopped
pump reads exactly 5.0. With *Water Flow* and *Water Pump* both off and the
register at 5.0, the integration reports 0 (2.2.1); otherwise calculated
thermal power, COP and thermal energy would count heat that is not there. The
register value stays visible as the attribute `register_value`.

## Heat goes negative during a defrost

During a defrost the unit takes heat out of the heating water: outlet below
inlet with the pump running, and input 48–49 (*Thermal Power (Reported)*)
negative. Both thermal powers and both COPs are negative then (2.2.3),
and *Thermal Energy (Calculated)* drops a little. That is what the defrost
costs, not a fault.

## A cold coil is not yet ice

To take heat from the air, the evaporator coil has to be colder than the air.
While the compressor ran (3–22 November 2026, steady running, defrosts left
out), the gap between *Outdoor Temperature* and the coil (*Temperature Before
Evaporator*) was small and steady, growing a little with the speed:

| Compressor speed | Outdoor − coil (median) | 97 % of the minutes below |
|---|---|---|
| up to 1,300 rpm | 2.9 K | 3.6 K |
| 1,300–1,500 rpm | 3.0 K | 3.9 K |
| 1,500–1,650 rpm | 3.3 K | 4.3 K |
| 1,650–1,800 rpm | 3.5 K | 4.7 K |

So **at 3 °C outside or colder the coil is below 1 °C in 97 % of the running
minutes**, and below 0 °C most of the time. That alone does not mean ice:

- **Ice needs moisture.** It only forms where the coil is below 0 °C *and*
  below the **frost point** of the air. At 2.5 °C outside the frost point is
  +1.9 °C at 95 % humidity, −0.2 °C at 80 %, −2.7 °C at 65 % and −4.7 °C at
  55 % (Magnus formula over ice). On the morning of 23 November the coil ran at
  −0.2 °C and no ice formed: dry air.
- **Ice shows in the gap.** Ice on the fins blocks the air, and the coil gets
  colder against the air. Before the defrost on 22 November at 10:54 the gap
  rose from 3.1 K to 5.7, 6.9 and 7.2 K within 25 minutes at 1,400–1,500 rpm,
  well above the normal 3–4 K; it fell back after the defrost.

**For automations:** throttling the compressor whenever the coil is below
about 1 °C throttles it all day on every cold day, whether ice forms or not.
On 23 November at 08:33 such a rule (the [example AutoTemp's
frost protection](automations.md#autotemp)) lowered the setpoint from 37 to
21 °C at 2.5 °C outside and held the compressor at 960 rpm, with a coil at
−0.6 °C in dry air. A rule that only reacts to ice needs three conditions:
coil below about 0.5 °C, coil below the frost point of the air, and the coil
more than about 5 K colder than the air; it releases once the gap is below
about 4 K. That rule is **being tested** on this unit from 23 November 2026,
with the humidity from the weather entity (see [cop-efficiency.md](cop-efficiency.md#what-is-being-tested-now));
the 5 K and 4 K are first estimates from two defrosts and will be checked
against the defrost counter (*Defrosts*, *Defrost Energy*, 2.3.0) over the
coming cold days.

## The electrical figures run high

Compared with the smart meter, the unit's *Electrical Power* (input 34–45)
reads **too high**, so every COP built on it comes out too low. At 31
compressor starts and stops (3–22 November 2026) the house meter moved by a
median **0.69 ×** the unit's figure (half between 0.67 and 0.75). At
1-second resolution, with the heat pump's steps told apart from the house by
the three phases (it moves all three at once), the error is mostly a constant
part while running: real ≈ 0.94 × unit − 355 W. At night, idle, it reports
49 W but draws **about 13 W** (nights before and after it was switched on on 23
October 2026); the preheating pulses come out at about 0.62 × (about 300 W by
the unit, about 180 W by the meter). Over whole days the real energy is
**0.71 ×** the unit's. For billing and for a COP to rely
on, use a separate meter. Details, and what it means for the COP:
[cop-efficiency.md](cop-efficiency.md). See also the
[README](../README.md#energy-registers-optional).

## Heating setpoints below 20 °C are not accepted

Writes below 20 °C to *Target Temperature Circuit 1* did not stick, although
LG's service manual gives 15–65 °C. The integration offers 20–60 °C (2.2.5). A
unit with a backup heater can go lower.

## Inputs without a sensor send 64887

A temperature input with nothing connected sends 64887, read signed −64.9 °C;
read unsigned before 2.2.3 it was recorded as 6488.7 °C. On this unit: *Flow
Temperature Circuit 2*, *DHW Temperature*, *Backup Heater Outlet Temperature*
and experimental input 30015. Their sensors show *unknown*.

## Room Air Temperature Circuit 1 is the plant room

Without a wired remote controller, input 30008 is the indoor unit's own sensor,
so it measures the room the unit is installed in. The dashboard labels it
*Technikraum*. Do not use *Control Method: Room Air Control* on such an
installation: the unit would regulate on the plant room. See the
[README](../README.md#notes).

## Cooling active is on while heating

Discrete input 10009 read `on` during heating for days. Do not build
automations on *Cooling active*. See the
[README](../README.md#binary-sensors).

## The water pump runs while Heating/Cooling is on

With *Heating/Cooling* switched on, the water pump runs, also at thermo off
with the compressor standing still. On this installation that is wanted, and
the switch stays on overnight (the stop automation only lowers the setpoint),
so the pump runs around the clock.

From 1 to 14 November 2026 *Flow Rate* never read 0, which it does as soon as
the pump stops (since 2.2.1). Every night from 00:00 to 05:00 the flow averaged
11.4–11.9 L/min, at 13 °C outside as at 0.7 °C, and about the same as by day:
no separate frost mode with more flow shows in the data; the pump runs at one
speed. During the fan runs of 13/14 November it did not change either (11.68
and 11.73 L/min against 11.68 L/min the hour before).

**Wish:** while the compressor is off, the pump could run slower than about
10 L/min: at thermo off it only has to keep the water moving, not carry heat,
and a slower pump would use less electricity. The pump speed can be set lower
on the unit itself, but then it reports **error 14**, presumably its low-flow
protection, which does not distinguish a running compressor from thermo off.
No Modbus register for the pump speed is known; the manual's register map has
none.
