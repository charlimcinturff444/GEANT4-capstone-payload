# Base CubeSat radiation model (fill in later)

A starter model for your payload. Right now it holds placeholder numbers, so it shows the
METHOD. Replace the placeholders as your team learns the real answers and re-run.

## Run it (needs Python with numpy, pandas, matplotlib)

    python cubesat_model.py config_12U.json            # shielding at each board and the payload
    python cubesat_model.py config_6U.json --out r6U   # same for 6U
    python cubesat_model.py config_12U.json --demo     # shows dose output, with FAKE numbers
    python cubesat_model.py config_12U.json --sweep payload --values 1 2 3 5
                                                       # what if the payload wall were 1/2/3/5 mm?

Results land in a folder (`model_output` by default): `shielding.png`, `summary.csv`, `rays.csv`.

## The config file = your fill-in form

Open `config_12U.json` in any text editor. Each block has a note saying what it is.

| Block | Fill in when you learn... |
|---|---|
| `satellite` | the real outer size, wall thickness, wall material |
| `solar_panels` | panel thickness (or turn them off) |
| `boards` | how many circuit boards, their size, spacing |
| `components` | payload box(es): size, wall thickness, material, position. Copy the block to add more |
| `extra_points` | any exact spot you want a reading for, e.g. one sensitive chip |
| `mission` | orbit label, mission length (years), what dose your parts can survive |
| `dose_curve` | the file name of your SPENVIS dose-depth curve (this is what turns shielding into dose) |

## Questions that unlock real numbers

1. What orbit (altitude, inclination)? -> gives you the dose-depth curve from SPENVIS
2. How long is the mission? -> `duration_years`
3. What electronics will the payload use, and what dose do they tolerate? -> `part_tolerance_krad`
4. What are the real structure and payload dimensions? -> `satellite`, `boards`, `components`

## Getting the dose-depth curve

Create a free account at spenvis.oma.be, define your orbit, and run the trapped proton/electron
and solar particle models plus the SHIELDOSE-2 dose-depth calculation. Export dose versus
aluminum thickness. Save it as a two-column CSV (thickness in mm, dose in krad), put the file next
to the config, and set `dose_curve > csv`. See `demo_dose_depth_NOT_REAL.csv` (in this
folder) for the file format. That file's numbers are fake.

## Limits

* Total ionizing dose only. Single-event effects are not covered.
* Boxes only: no curved parts, connectors, or wiring.
* Aluminum equivalence uses density ratio (the method in Seo et al. 2012). It is approximate.
* The older models in that paper (AP-8/AE-8) have newer replacements (AP-9/AE-9) available in SPENVIS.
* The Geant4 version of the ray-tracer is in the `cubesat_shield` folder; this Python model gives
  the same shielding numbers and is easier to modify.
