# Geant4 quickstart (shield.cc)

Goal: build and run the Geant4 ray-tracer, then check it against the tested Python model.

## A. Get Geant4 (once)

**Mac or Linux**
1. Install Miniforge (gives you `conda`): https://github.com/conda-forge/miniforge
2. In a terminal:
       conda create -n g4 -c conda-forge geant4 cmake make compilers
       conda activate g4
3. Check it worked:  `geant4-config --version`  (should print a version number)

**Windows** (Geant4 is not on conda for Windows, so use Linux inside Windows)
1. Open PowerShell as Administrator:  `wsl --install`   then restart the PC.
2. Open the "Ubuntu" app, create a username/password, then follow the Mac/Linux steps above inside Ubuntu.
3. Your Windows Desktop is at  /mnt/c/Users/<your name>/Desktop  inside Ubuntu.

## B. Build

    cd /path/to/cubesat_shield
    mkdir build && cd build
    cmake ..
    make

If cmake says it cannot find Geant4, run this instead of `cmake ..`:
    cmake -DGeant4_DIR=$CONDA_PREFIX/lib/cmake/Geant4 ..

## C. Run

    ./shield                      # writes rays.csv  (6 points x 1800 rays = 10800)
    cd ..
    pip install numpy pandas      # if needed
    python tid.py build/rays.csv demo_dose_depth_NOT_REAL.csv

(the curve file is FAKE; we only use it so tid.py prints the shielding columns)

## D. Did it work? Compare with these (from the tested Python model)

    point             min t (mm)   median t   % sky < 10 mm
    pcb1                 2.83         8.1         62.2
    pcb2                 2.83         8.8         64.4
    pcb3                 2.83         8.9         59.8
    pcb4                 2.83         9.7         51.6
    pcb5                 2.83        10.3         42.4
    payload_center       5.39         6.6         96.7

Matching (to about 0.1) means the Geant4 build works and is tracing correctly.
Tiny differences are fine. Big differences mean a bug: send me the numbers.
