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
- [The electrical figures run high](#the-electrical-figures-run-high)
- [Heating setpoints below 20 °C are not accepted](#heating-setpoints-below-20-c-are-not-accepted)
- [Inputs without a sensor send 64887](#inputs-without-a-sensor-send-64887)
- [Room Air Temperature Circuit 1 is the plant room](#room-air-temperature-circuit-1-is-the-plant-room)
- [Cooling active is on while heating](#cooling-active-is-on-while-heating)
- [The water pump runs in frost from time to time, at full power](#the-water-pump-runs-in-frost-from-time-to-time-at-full-power)

## At night: fan runs and compressor preheating

**Seen** on 13/14 November 2026, outdoor about 1.5–4.5 °C, compressor off all
night. The house meter showed an hour of square pulses, about 200 W on one
phase, one minute on, one minute off, from 23:56 to 01:00; at each end a block
of about 250 W for two minutes. Before and after: the standby (about 50 W by
the unit's own figure) and the fridge.

**The 250 W blocks are the outdoor unit's fan.** At 23:55:30 *Outdoor
Temperature* fell from 4.6 to 1.4 °C within 90 s and the evaporator coil from
7.3 to 3.1 °C; at 00:58 the same, 3.6 → 1.4 °C and 6.2 → 2.7 °C. Only moving air
does that; afterwards both crept back up. The unit runs its fan briefly to
measure the real air temperature (see the next finding). The water pump's
frost runs at full power may be part of these blocks as well
([below](#the-water-pump-runs-in-frost-from-time-to-time-at-full-power)); the
temperature drops only prove the fan.

**The pulses heat the compressor.** The unit's own *Electrical Power* read
about 300 W on the polls that hit an "on" minute (00:12, 00:27, 00:40, 00:45)
and 46–49 W otherwise, with the compressor at 0 rpm throughout. Over the same
hour, at about 2 °C outside, *Hot Gas Temperature* rose from 15 to 20 °C (22 °C
by 01:07) and *Suction Temperature* from 13.0 to 14.7 °C. With the compressor
standing still, that heat can only come from the unit heating the compressor
(a crankcase heater, or current through the motor windings), which keeps the
oil warm so refrigerant does not dissolve into it before the next start. The
coil warming back up afterwards matches the still air after the fan run, so a
drain pan heater is the less likely explanation.

**The sequence:** fan run → real outdoor temperature below a threshold of
roughly 2–3 °C → about an hour of preheating → fan run again. In ten days of
history such phases appeared only on nights at or below about 5 °C (as read in
still air), never on the mild nights in between.

**Cost:** about 200 W at half duty for an hour, roughly 0.1 kWh per phase; a
few tenths of a kWh on a cold night. Normal, and it protects the compressor.

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

## The electrical figures run high

Compared with the smart meter, the unit's *Electrical Power* (input 34–45)
usually reads **too high**, so every COP built on it comes out too low. Last
night again: about 300 W by the unit, about 200 W by the meter for the same
pulses. For billing and for a COP to rely on, use a separate meter. See the
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

## The water pump runs in frost from time to time, at full power

In frost the water pump does not run all the time: it starts from time to
time and then runs at full power, to keep the water in the pipes moving and
from freezing. Whether these runs coincide with the fan runs above has not
been checked yet; *Flow Rate* and *Water Pump* show it.
