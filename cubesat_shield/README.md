# CubeSat shielding ray-tracer (Geant4)

Implements the shielding step of Seo et al., *Current Applied Physics* 12 (2012) 1541-1547.

**Workflow**

1. `shield` (C++/Geant4): fires geantinos from each calculation point in 1800 equal-solid-angle directions and records the aluminum-equivalent shielding thickness along each ray -> `rays.csv`
2. SPENVIS (web): export a dose-depth curve (dose vs. aluminum thickness) for your orbit -> `dose_depth.csv`
3. `tid.py` (Python): combines them with Eq. 1 -> TID at each point

## Build

You need Geant4 (10.7 or newer) installed and its environment set up.

```bash
source /path/to/geant4-install/bin/geant4.sh   # sets up Geant4 paths
mkdir build && cd build
cmake ..
make
```

If you don't have Geant4 yet, the conda-forge package is the easiest route:
`conda create -n g4 -c conda-forge geant4 cmake compilers` then `conda activate g4`.

## Run

```bash
./shield              # 30 x 60 = 1800 sectors, writes rays.csv
./shield 60 120 fine.csv   # finer sky grid, custom output name
python ../tid.py rays.csv dose_depth.csv
```

`dose_depth.csv` is two comma-separated columns: aluminum thickness in mm, and dose
(any unit, e.g. krad/year). The answer comes out in the same unit.

## Before you trust any number

- **Edit the geometry.** Every dimension in `DetectorConstruction::Construct()` is a placeholder.
  Replace the structure, PCB stack and payload box with your real design.
- **Add your own calculation points** by adding `fPoints.push_back({...})` lines next to the PCBs and payload.
- **Reproduce the paper first.** Build their 2U, 3 mm-payload case (200 x 100 x 100 mm, 5 PCBs at 15 mm pitch,
  70 x 70 x 60 mm payload box with 3 mm walls) and check you get close to their LEO and GEO table values
  before moving to the 12U.
- **Use current environment models.** The paper used AP-8/AE-8; SPENVIS also offers AP-9/AE-9.
- This gives total ionizing dose only, not single-event effects.

## Sanity checks on the ray output

- A point fully enclosed by 2 mm aluminum walls should show a minimum thickness of about 2 mm.
- `rays.csv` has one row per ray; every point should have exactly 1800 rows.
- Thickness should rise toward directions that pass through more hardware (the PCB stack, the payload box).
