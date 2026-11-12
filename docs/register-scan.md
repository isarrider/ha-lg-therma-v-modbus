# Register scan of the R290

A read-only scan of the Modbus address space of a LG Therma V R290 9 kW (HN1639HC NK0, slave 33, Modbus TCP via gateway), 2026-10-03. One request per address, one connection per request, 1 s timeout. Nothing was written.

An address that the device does not serve is not answered at all (timeout) instead of getting a Modbus exception. A block read that contains such an address is dropped as a whole, which is why input register 15 breaks a bulk read.

## What answers

| Type | Scanned | Answers | In the manual |
|---|---|---|---|
| Coils (FC01) | 0–23 | 0–5 | 00001–00006 |
| Discrete inputs (FC02) | 0–39 | 0–16 | 10001–10017 |
| Input registers (FC04) | 0–63, 9990–10000 | 0–14, 16–24, 63, 9997, 9998 | 30001–30014, 39998, 39999 |
| Holding registers (FC03) | 0–63 | 0–22, 62, 63 | 40001–40010 |

Coils and discrete inputs match the manual exactly. Input and holding registers answer on more addresses than the manual lists.

## Not in the manual, used by this integration

Input registers 16–24 (30017–30025) are not in the manual's table either. Meaning and scale come from community projects and from measurement:

| Register | Meaning | Scale |
|---|---|---|
| 30017 | Liquid gas temperature | ×0.1 °C |
| 30019 | Suction temperature | ×0.1 °C |
| 30020 | Hot gas temperature | ×0.1 °C |
| 30021 / 30022 | Temperature before / after evaporator | ×0.1 °C |
| 30023 / 30024 | High / low pressure | ×0.01 bar (raw is kPa) |
| 30025 | Compressor frequency | ×60 = rpm (raw is Hz) |

The pressure scale was confirmed against live values: raw 768 at standstill (7.68 bar, high and low side equalised), about 2200 under full load (22 bar).

## Answers, but nobody knows what it is

Read on 2026-10-03 with the compressor stopped (outdoor 29 °C):

| Register | Raw value | Note |
|---|---|---|
| Input 30015 (14) | 64887 | −649 signed; ×0.1 = −64.9 °C, the pattern of a temperature channel without sensor (a forum report shows the same on 30011) |
| Input 30018 (17) | 12000 | no reading, lies between two temperatures |
| Input 30064 (63) | 65534 | 0xFFFE, probably an edge value |
| Holding 40011–40023 | 0 | 13 registers, unused or reserved |
| Holding 40063 | 65534 | 0xFFFE |
| Holding 40064 | 0 | |
| Input 39999 | 8208 | 0x2010; the manual lists only 0, 3, 4, 5, 6 here |

The optional *Experimental registers* setting of the integration records these over time so they can be compared with the compressor, temperatures and defrost cycles.

## Evaporator and suction sensors

Ten days of history of a 12 kW unit (November 2026, compressor speed, suction, both evaporator temperatures and the low pressure, every value Home Assistant recorded):

* **30021 and 30022 are the same sensor.** At all 3965 points where either changed, both had the same value a few seconds later -- not 0.1 K apart, not at start-up, standstill or defrost. (Raw exports show them a few milliseconds apart only because each entity is written on its own.) The integration keeps both, but *Temperature after Evaporator* starts disabled on new installations.
* **It is the evaporator coil.** With the compressor running it reads a median 1.1 K (10th-90th percentile 0.5-3.8 K) above the boiling temperature of propane at the low pressure -- what a sensor on the coil, where the refrigerant boils, should read.
* **The pressures are gauge pressures.** That match only holds with the low pressure read as bar above atmospheric (+1 bar for absolute). Read as absolute, the coil would be about 8 K warmer than boiling propane, which is not possible while it evaporates.
* **Suction (30019) is a separate sensor.** With the compressor running for more than 15 minutes it reads a median 0.3 K (90th percentile 3.4 K) above the coil: the superheat the expansion valve keeps small. At standstill it is about 8 K warmer than the coil, as the suction line warms inside the unit while the coil follows the outdoor air.

## Does not answer

Holding 24 (40025, "power limit" in basti242's YAML) and coil 6 (00007, "active power limitation") get no answer on this unit.

They are documented, though not in the manual this scan was checked against: the installation manual of a 12 kW unit lists coil **00007** *Wirkleistungsbegrenzung* — *0: nicht verwendet / 1: Leistung gemäß 40025 begrenzen* — so 40025 holds the power limit and 00007 switches it on. Whether a 12 kW unit answers on them, and whether the limit takes effect, has not been tested yet. The integration reads and writes them only behind the *Power limit* option (off by default).

## Sources checked

The installation manual (Modbus memory map, pp. 157–160), basti242's YAML setup, [32u-nd/ha-heatpump-fsm](https://github.com/32u-nd/ha-heatpump-fsm), [MarinX/lg-thermav-mcp-server](https://github.com/MarinX/lg-thermav-mcp-server) and the simon42 forum thread. None of them explains the registers in the last table. MarinX scales the pressures by 0.1, which does not match measurement here.
