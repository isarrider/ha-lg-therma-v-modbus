# Example automations: a heating day with AutoTemp

Three automations, each in its own file, that run circuit 1 (radiators) through the day: the compressor starts once in the morning, heats at a chosen speed cap until the water reaches a target set by the outdoor temperature, and then holds it, instead of switching on and off.

| Time | Automation | What happens |
|---|---|---|
| 08:30 | [Start](#start-0830) | Heating on, outlet control, 60 °C: the compressor starts reliably |
| ~08:31 | [AutoTemp](#autotemp) (target) | Once the compressor has run 1 minute: inlet control, setpoint straight to the target (37 °C at 0 °C outside to 32 °C at 15 °C) |
| until 17:00 | [AutoTemp](#autotemp) | The unit heats at the max compressor modulation until the water is at the target, then holds it on its own; frost protection only for real ice, a thermo off guard and the oil boost as needed |
| 17:00 | – | AutoTemp stops; the setpoint stays where it is |
| 17:30 | [Stop](#stop-1730) | Setpoint 20 °C, max compressor modulation 41 %: the unit reaches thermo off and AutoTemp treats it as off |

They were written for a 12 kW unit and are **in testing** on it since 23 November 2026; why they look like this is in [cop-efficiency.md](cop-efficiency.md) (faster is more efficient up to about 1,800 rpm) and [findings.md](findings.md#a-cold-coil-is-not-yet-ice) (a cold coil is not yet ice). The [earlier version](#the-earlier-version) held the compressor back and is described at the end.

Entity ids are the defaults (`…lg_therma_v_r290_…`); if you renamed yours, adjust them. The stop automation needs the *Max compressor modulation* option; leave its second action out without it. The start and stop times can be changed freely: AutoTemp takes over 1 minute after the compressor starts, whenever that is (before 17:00), and stops as soon as the setpoint is at 20 °C.

**To use them:** open the file, copy its content, then *Settings → Automations & scenes → Create automation → Create new automation → ⋮ → Edit in YAML*, paste, *Save*.

To see on a dashboard what they are doing and why, add the cards from [On the dashboard](#on-the-dashboard).

## Before you start: the thermo on/off hysteresis and the lowest setpoint

The unit switches the compressor off when the water it regulates on (the inlet or the outlet, depending on the control method) is the hysteresis above the setpoint, and on again when it is the hysteresis below it. The hysteresis is set in the installer menu of the wired remote, *Th On/Off Variable, Heating Water*, in steps of 1–4 °C; it is not available over Modbus.

AutoTemp is tuned for **±4 °C**: its thermo off guard raises the setpoint once the inlet is `emergency_gap` (3 °C) above it, a margin of 1 °C, and frost protection never lowers it more than `frost_max_gap` (2.5 °C) below the inlet. With a smaller hysteresis, lower both so they stay below it.

The lowest heating setpoint the unit accepts is **20 °C** with the backup heater switched off; lower values are stored as 20 °C. AutoTemp therefore uses 20 °C as "off" and never sets less than 21 °C (`floor`) itself.

## Start (08:30)

The YAML is its own file: [therma-v-start.yaml](therma-v-start.yaml).

It switches heating on, sets **outlet control** and the circuit 1 setpoint to 60 °C, so the compressor starts reliably. The time is in its trigger (`at: '08:30:00'`).

The start must set **outlet control**: AutoTemp takes over from there (it switches to inlet control itself).

## AutoTemp

The YAML is its own file: [autotemp-heat-circuit-1.yaml](autotemp-heat-circuit-1.yaml). Everything worth tuning is at the top (`trigger_variables`) or the bottom (`variables`) of it.

What it does until 17:00 while the compressor runs:

- **Target.** Once the compressor has run 1 minute on outlet control (the warm-up of the start automation), it switches to inlet control and sets the setpoint straight to the target: `target_cold` (37 °C) at `outdoor_cold` (0 °C) or colder, `target_warm` (32 °C) at `outdoor_warm` (15 °C) or warmer, linear in between, from the unit's outdoor temperature, rounded down. Inlet control first, then the setpoint: the other way round the unit would briefly be on outlet control with a lower setpoint, which is thermo off. The unit then heats at the max compressor modulation until the inlet is there and holds it on its own, throttling itself. With inlet control the water settles about 1–1.5 K above the setpoint. Every 5 minutes it follows the target as the outdoor temperature changes, up and down, also while the water is still heating up (before 24 November it only lowered the setpoint once the inlet had come down to it, so a morning target stayed all day when it got milder).
- **Frost protection, only for ice.** The coil (`temperature_before_evaporator`) is below 0 °C most of the time on a cold day while heating; that alone does not throttle. It acts when the coil is icing up: below `frost_coil` (0.5 °C), below the **frost point** of the air (from the temperature and humidity of `weather_entity`: dry air does not ice even with the coil well below 0 °C), and more than `frost_gap` (5 K) colder than the outdoor air for 2 minutes (normal while running is 3–4 K; ice on the fins blocks the air and pushes the gap up). Then it sets the setpoint just below the inlet, so the unit throttles at once, and lowers it 1 °C every 2 minutes, never below `floor` and never more than `frost_max_gap` below the inlet. It goes straight back to the target once the gap is below `frost_release_gap` (4 K), or the coil above `frost_coil` or the frost point, for 5 minutes. Between 4 and 5 K nothing changes. Without humidity data the frost point check is skipped (coil and gap only).
- **Thermo off guard.** When the inlet is `emergency_gap` (3 °C) above the setpoint for 20 seconds (the house takes less than the compressor's minimum), it raises the setpoint by 1 °C, up to `ceiling` (40 °C), also during frost protection. Once the inlet is `down_gap` (1 °C) below it for 5 minutes, it lowers it again, never below the target.
- **Defrost.** During a defrost and for 5 minutes after it, nothing happens: the defrost cools the water, and the dip would otherwise mislead it.
- **Oil boost.** After about 60 minutes below roughly 1500 rpm the unit spins the compressor up to about 3600 rpm for a moment to bring the compressor oil back (oil return). After 55 minutes below `low_rpm`, AutoTemp raises the setpoint to inlet + 3 °C (up to `boost_ceiling`, 45 °C), waits until the compressor has been at or above `low_rpm` for 60 seconds, then goes back to the setpoint from before the boost. With the target running at 1,700–1,900 rpm this rarely comes up any more.
- **Off.** At or below `off_setpoint` (20 °C) it does nothing at all. Setting the slider to 20 °C (its lowest position) by hand switches the unit off for the rest of the day without AutoTemp working against it; this also ends a running oil boost.

It re-checks every 5 minutes, so it catches up after a restart of Home Assistant or after being switched on again.

### What to know

- **The speed comes from the max compressor modulation.** On the 12 kW unit 41 % gave 1,800 rpm at 3 °C outside and 1,860–1,920 rpm at −1.5 °C; 45 % about 1,980 rpm. The COP is best at about 1,700–1,800 rpm with the water temperature held and does not improve above it ([cop-efficiency.md](cop-efficiency.md#the-catch-more-heat-needs-warmer-water)); 41 % is the setting in testing. Without the *Max compressor modulation* option the unit runs at whatever speed it chooses.
- **The target is the comfort knob.** If the house gets too warm, lower `target_cold` and `target_warm` by 1 °C; each kelvin of cooler water is worth about 0.1 COP. On the 12 kW unit 38 / 33 °C made the house almost too warm on the first day; 37 / 32 °C is the setting in testing.
- **Defrosts still happen.** Below about 0 °C in moist air the unit defrosts on its own about once an hour (on 24 November after 35 minutes at −1 °C, a gap of only about 4.2 K): about 3 minutes, about 0.25 kWh of heat. Frost protection is there for fins that clog (a gap above 5 K), not to prevent every defrost; throttling all day to avoid them costs more than they do.
- **The thresholds are first estimates** from a few defrosts on one unit; the normal gap grows with the speed (about 3.4 K at 1,400 rpm, about 4 K at 1,800–2,000 rpm). *Settings → Automations → AutoTemp → ⋮ → Traces* shows each run with the trigger, the branch taken and the values it saw.
- **The oil boost is a finding from one unit, not documented by LG.** If the hourly spikes still come at low speed, try a higher `low_rpm` (e.g. 1600) and a shorter wait in the `oil_boost` trigger (e.g. 50 minutes).
- **Switching to outlet control by hand during the day** is undone within a minute (the target step switches back to inlet control). Set the slider to 20 °C or switch the automation off first.
- **After 17:00 it does nothing.** Between 17:00 and the stop nothing adjusts the setpoint; the unit holds the last one. A start after 17:00 stays on outlet control at 60 °C until the stop.
- **Error log entries while the editor is open.** With the automation open in the editor, Home Assistant may log `'speed_entity' is undefined` for the two templates of the oil boost's `wait_for_trigger`: the editor subscribes to them without the automation's variables. When the automation runs, they have them.

## On the dashboard

All three automations explain every change of the setpoint in one line in Home Assistant's logbook, attached to the circuit 1 setpoint, so the change and its reason stand next to each other. Nothing to set up; the logbook is part of Home Assistant's default configuration.

| Automation | Example line in the logbook |
|---|---|
| Start | *Therma V start* heating on, outlet control, 60 °C |
| AutoTemp, target | *AutoTemp* target: inlet control, 37 °C (outdoor −2.0 °C, inlet 18.4 °C) |
| AutoTemp, frost protection | *AutoTemp* frost protection: lowered to 30 °C (coil −6.8 °C, 5.4 K below outdoor −1.4 °C, frost point −3.1 °C) |
| AutoTemp, back to the target | *AutoTemp* back up to 37 °C (target 37 °C, coil −1.4 °C, 3.9 K below outdoor) |
| AutoTemp, thermo off guard | *AutoTemp* raised to 38 °C: inlet 40.1 °C, 3.1 K above, close to thermo off · lowered to 37 °C: inlet 36.8 °C, 1.2 K below for 5 min (target 37 °C) |
| AutoTemp, oil boost | *AutoTemp* oil boost: 38 °C after 55 min below 1500 rpm, then oil boost over (speed held): back to 35 °C |
| Stop | *Therma V stop* setpoint 20 °C (thermo off, AutoTemp off), max modulation 41 % |

Two cards (*Edit dashboard → Add card → Manual*):

- **What it did and why**, the logbook of the setpoint: its changes (*changed to 37*) with the line explaining each, newest first.

  ```yaml
  type: logbook
  title: AutoTemp
  target:
    entity_id: number.lg_therma_v_r290_target_temperature_circuit_1_radiators
  hours_to_show: 24
  ```

- **What it is doing now and next**, [autotemp-status-card.yaml](autotemp-status-card.yaml): *AutoTemp: heating up* or *holding* with the setpoint, the target, the inlet and where the thermo off guard raises next (*raises from 40 °C*); *warm-up* with the target it is about to set; *watching ice* while thin ice forms but the gap has not stayed above 5 K (nothing throttled); *frost protection* once it has lowered the setpoint, with the coil, the gap and the frost point; *back to the target*; *paused (defrost)*, *waiting for the compressor*, *done for today (after 17:00)*, *off (setpoint 20 °C)* or *disabled*. It is worked out on the dashboard from the same states AutoTemp uses, so it also says why AutoTemp is idle. Below it, a small table says when the compressor last ran and the last defrost ended and how long each lasted (*running since 08:30 · 7.0 h*, *ended 6.3 h ago (09:10) · 3 min*; needs the *Compressor statistics* option), and one line gives the **outdoor temperature below which ice can form** on the coil: below 0 °C and below the frost point on the coil, so the frost point (or 0 °C, whichever is lower) plus the coil's gap to the air (now while running, else a typical 3.5 K): *Ice possible below 0.4 °C outside (now 1.1 °C: no) · frost point −3.3 °C, coil 3.7 K below the air*. The times come from when the compressor and defrost states last changed, so after a restart of Home Assistant they count from the restart. The thresholds, the target curve and the weather entity are written into the card; change them there too if you change them in AutoTemp.

The card uses the automation's entity id `automation.autotemp_heat_circuit_1`, which it gets when saved with the alias from the file; if yours differs (*Settings → Automations → AutoTemp → ⋮ → Information → Settings*), adjust it in the card.

### AutoTemp through the day (optional)

The status card shows only the moment. To see the whole day as a coloured bar next to *Compressor* and *Defrost* (*off → waiting for the compressor → warm-up → heating up → watching ice → heating up → paused (defrost) → … → holding → done for today → off*), the status has to be an entity, so Home Assistant records it: a **template sensor**.

1. *Settings → Devices & services → Helpers → Create helper → Template → Template a sensor*.
   - **Name:** `AutoTemp status`.
   - **State template:** the content of [autotemp-status-template.jinja](autotemp-status-template.jinja). The preview at the bottom of the dialog shows the current state, e.g. *off* in the evening.
   - Leave *unit of measurement*, *device class* and *state class* empty, so the history is drawn as a bar, not as a line.
   - **Device** (optional): *LG Therma V R290*, so the sensor sits with the heat pump.
   - *Submit*.
2. Look up its entity id: *Developer tools → States*, filter `autotemp`. Without a device it is `sensor.autotemp_status`; with the device it takes the device's name (and area) as a prefix, e.g. `sensor.heatpump_lg_therma_v_r290_autotemp_status`.
3. Add it as a row to a history graph, e.g. below *Defrost* in the full dashboard's overview:

   ```yaml
   - entity: sensor.autotemp_status   # the id from step 2
     name: AutoTemp
   ```

It shows the same states as the first line of the status card, in the same order: *disabled*, *off*, *done for today*, *paused (defrost)*, *waiting for the compressor*, *warm-up*, *frost protection* or *watching ice*, *back to the target*, *heating up*, *holding*. The history starts when the sensor is created. Short sections, like the minute of warm-up or a defrost, are too narrow for a label; hovering or tapping one shows its name and time span.

## Stop (17:30)

The YAML is its own file: [therma-v-stop.yaml](therma-v-stop.yaml).

It sets the circuit 1 setpoint to 20 °C, the unit's lowest value with the backup heater off: with inlet control and a hysteresis of ±4 °C the unit switches off once the inlet is at 24 °C, which after a day of heating it always is. 20 °C is also "off" for AutoTemp, so it stops adjusting at once, even before 17:00. Heating stays switched on, so on a very cold night the unit restarts when the inlet drops below 16 °C and heats until it is back at 24 °C (safety net). It also resets the max compressor modulation to 41 %, in case it was changed by hand during the day, so a restart at night and the next day run at 41 % too. The time is in its trigger (`at: '17:30:00'`).

## The earlier version

Until 23 November 2026 the example held the compressor back instead (start at 08:00, stop at 18:00, max modulation 40 %):

- **Cold start** on outlet control with the setpoint just below the outlet while the inlet was below 22 °C, then a **kick-in** to inlet control just below the inlet;
- **following the inlet** (up 1 °C at 2.8 °C above, down at 1 °C below for 5 minutes) and a **morning ramp** that pulled the setpoint to 33–38 °C by 13:00;
- **frost protection** whenever the coil was below 1 °C.

It kept the compressor at 1,000–1,400 rpm for much of the day, which turned out to be the least efficient range on this unit ([cop-efficiency.md](cop-efficiency.md#the-catch-more-heat-needs-warmer-water)), and the frost rule throttled all day below about 3 °C outside, ice or not ([findings.md](findings.md#a-cold-coil-is-not-yet-ice)). The files of that version are in the repository history (`git log -- docs/autotemp-heat-circuit-1.yaml`).
