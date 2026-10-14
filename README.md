# GNAT4-capstone-payload

**Windows guide: running the CubeSat shielding model with Geant4**


Download the files and place them like this:

```text
C:\Users\YOURNAME\Downloads\cubesat_shield\
    shield.cc
    CMakeLists.txt
    tid.py
    demo_dose_depth_NOT_REAL.csv

C:\Users\YOURNAME\Downloads\base_model\
    cubesat_model.py
    config_12U.json
    config_6U.json
```

---


 Open the `base_model` folder in File Explorer. Click the address bar at the top, type `cmd`, and press Enter. A black Command Prompt window opens in that folder.


4. Run the model:

   ```bat
   py cubesat_model.py config_12U.json
   ```

A table prints and a new folder called `model_output` appears. Open `model_output\shielding.png` to see the sky maps.

**To change the satellite:** open `config_12U.json` in Notepad, change a number, save, and run step 4 again. Keep the commas and quotation marks exactly as they are.

---

## Part 2: Install WSL (Ubuntu inside Windows)

1. Right-click **Windows PowerShell** and choose **Run as administrator**.
2. Type:

   ```powershell
   wsl --install
   ```

3. Wait for it to finish (several minutes). Restart the computer when asked, or restart afterward.
4. After the restart, an Ubuntu window opens by itself (if not, open Start and search for **Ubuntu**). Wait for it to finish setting up. It then asks you to create a username and password.
   - Pick a simple lowercase username.
   - When you type the password nothing appears on screen; that is normal.
   - Remember the password, because you will need it for the `sudo` command.
5. Check that it is WSL 2. In PowerShell, type:

   ```powershell
   wsl -l -v
   ```

   You should see Ubuntu with `VERSION 2`.

> **If `wsl --install` only prints a help message**, your Windows is older or WSL is not enabled. Open Start, search for **Turn Windows features on or off**, tick **Windows Subsystem for Linux** and **Virtual Machine Platform**, restart, then run `wsl --install` again. If it complains about virtualization, see [Part 10](#part-10-troubleshooting).

---

## Part 3: Set up Geant4 inside Ubuntu

> From now on, type these commands in the **Ubuntu window**, not PowerShell.

1. Update Ubuntu (enter your password when asked):

   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. Install Miniforge, a tool that downloads Geant4 for you:

   ```bash
   curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
   bash Miniforge3-$(uname)-$(uname -m).sh
   ```

   Press Enter to scroll the license, type `yes` when asked, accept the default location, and answer `yes` when it asks about initializing conda.

3. Close the Ubuntu window and open it again so conda is active. You should see `(base)` at the start of the prompt.
4. Create an environment with Geant4, the build tools, and the Python packages. The download is large, so expect 10 to 30 minutes:

   ```bash
   conda create -n g4 -c conda-forge geant4 cmake make compilers numpy pandas matplotlib
   ```

   Type `y` when asked to proceed.

5. Activate it and test:

   ```bash
   conda activate g4
   geant4-config --version
   ```

   A version number such as `11.x` means Geant4 is installed.

> **Important:** You must run `conda activate g4` every time you open a new Ubuntu window.

Our program does not need Geant4's separate data files, because it only moves non-interacting test particles. If a later Geant4 program asks for data files, ask for help at that point.

---

## Part 4: Copy your project into Ubuntu

Working inside Ubuntu's own folders is much faster than working on the Windows drive.

1. Find your Windows username as Ubuntu sees it:

   ```bash
   ls /mnt/c/Users
   ```

2. Copy both folders (replace `YOURNAME`):

   ```bash
   mkdir -p ~/capstone
   cp -r /mnt/c/Users/YOURNAME/Downloads/cubesat_shield ~/capstone/
   cp -r /mnt/c/Users/YOURNAME/Downloads/base_model ~/capstone/
   ```

3. Go into the Geant4 folder and check the files are there:

   ```bash
   cd ~/capstone/cubesat_shield
   ls
   ```

   You should see `CMakeLists.txt`, `shield.cc`, `tid.py`, and the demo csv file.

---

## Part 5: Build the Geant4 program

1. Make a build folder and configure it:

   ```bash
   mkdir build
   cd build
   cmake ..
   ```

   The last lines should say `Configuring done` and `Generating done`.

   If cmake says it cannot find Geant4, run this instead of `cmake ..`:

   ```bash
   cmake -DGeant4_DIR=$CONDA_PREFIX/lib/cmake/Geant4 ..
   ```

2. Compile:

   ```bash
   make
   ```

   It should end with `Built target shield`. If you see lines containing the word `error`, copy the first few error lines and ask for help. Because this program has not been compiled yet by its author, a small fix may be needed.

---

## Part 6: Run it and check it

1. Still inside the `build` folder:

   ```bash
   ./shield
   ```

   A Geant4 banner with the version number appears first (normal), then `Tracing 10800 rays`, then `Wrote rays.csv`. It takes seconds to a minute.

2. Summarize the results:

   ```bash
   cd ..
   python tid.py build/rays.csv demo_dose_depth_NOT_REAL.csv
   ```

   > **Note:** The curve file is **FAKE**. It is only there so the script runs. Ignore the TID column and look at the shielding columns.

3. Compare with this reference table, produced by the tested Python model:

   | Point | Min (mm) | Median (mm) | % of sky under 10 mm |
   |---|---|---|---|
   | pcb1 | 2.83 | 8.1 | 62.2 |
   | pcb2 | 2.83 | 8.8 | 64.4 |
   | pcb3 | 2.83 | 8.9 | 59.8 |
   | pcb4 | 2.83 | 9.7 | 51.6 |
   | pcb5 | 2.83 | 10.3 | 42.4 |
   | payload_center | 5.39 | 6.6 | 96.7 |

   If yours match to about 0.1, the Geant4 build works. If they are far off, send me your table.

### About Geant4 messages

- Lines surrounded by rows of **W** characters and mentioning `G4Exception` are **warnings**, and are often harmless if `rays.csv` was written.
- Lines surrounded by rows of **E** characters are **fatal errors** and mean the program stopped.

---

## Part 7: See pictures and open files from Windows

The Geant4 program writes numbers (`rays.csv`), not pictures. The pictures come from the Python model, which you can also run inside Ubuntu:

```bash
cd ~/capstone/base_model
python cubesat_model.py config_12U.json
explorer.exe model_output
```

The last command opens that Ubuntu folder in a normal Windows File Explorer window, where you can double-click `shielding.png`.

You can also reach your Ubuntu files from Windows by typing this in the File Explorer address bar (replace `YOURLINUXNAME` with the Ubuntu username you chose in Part 2):

```text
\\wsl.localhost\Ubuntu\home\YOURLINUXNAME\capstone
```

---

## Part 8: Put in your own numbers

**Easiest editor:** install [Visual Studio Code](https://code.visualstudio.com) on Windows, open it, and install the extension called **WSL**. Then, in Ubuntu, go to your folder and type `code .` to open it in VS Code.

### Python model

Edit `config_12U.json` (each block has a note explaining it) and rerun:

```bash
python cubesat_model.py config_12U.json
```

### Geant4 program

Open `shield.cc` and find the block commented `PLACEHOLDER DIMENSIONS` inside `DetectorConstruction::Construct`. Change the numbers (they are in mm), then rebuild and rerun:

```bash
cd ~/capstone/cubesat_shield/build
make
./shield
```

To add your own measurement point (for example, one sensitive chip), find the line `return worldPV;` near the end of `Construct` and add this just above it:

```cpp
fPoints.push_back({"my_chip", G4ThreeVector(10*mm, 0, -50*mm)});
```

> **Tip:** Use the same dimensions in both programs so that you can compare their results.

---

## Part 9: Every-time routine

1. Open **Ubuntu** from the Start menu.
2. Activate the environment:

   ```bash
   conda activate g4
   ```

3. Go to the build folder:

   ```bash
   cd ~/capstone/cubesat_shield/build
   ```

4. Rebuild (only needed after you edit `shield.cc`):

   ```bash
   make
   ```

5. Run:

   ```bash
   ./shield
   ```

6. Summarize (once you have a real dose-depth curve):

   ```bash
   cd ..
   python tid.py build/rays.csv YOUR_REAL_CURVE.csv
   ```

---

## Part 10: Troubleshooting

| Symptom | Fix |
|---|---|
| `py is not recognized` | Reinstall Python and tick **Add python.exe to PATH**, or try `python` instead of `py` |
| `wsl --install` fails and mentions virtualization | Restart and enter your BIOS/UEFI setup (the key is shown at startup, often F2, F10 or Del). Enable Intel VT-x or AMD-V (SVM Mode), save, and boot. In Task Manager, Performance tab, CPU, Virtualization should say **Enabled** |
| School-managed laptop blocks WSL | Ask your IT department, or use the Python model (Part 1) and run Geant4 on a lab computer or Linux machine |
| `conda: command not found` | Close and reopen Ubuntu. If it persists, run `source ~/.bashrc` |
| Prompt does not show `(g4)` | Run `conda activate g4` |
| cmake cannot find Geant4 | Use the `-DGeant4_DIR` command in [Part 5](#part-5-build-the-geant4-program) |
| `make` shows errors | Copy the first error lines and send them |
| `./shield: No such file` | You are not in the build folder, or `make` did not finish. Run `cd ~/capstone/cubesat_shield/build` and then `make` |
| Numbers do not match the table | Send me your table |
| `ModuleNotFoundError` for numpy inside Ubuntu | Run `conda activate g4` first |
| Odd behavior with files stored on the Windows drive | Work from `~/capstone` inside Ubuntu, not from `/mnt/c` |

---

## Part 11: What this does and does not tell you

- It estimates **total ionizing dose (TID) shielding only**, not single-event effects.
- All dimensions are **placeholders** until your team has the real design.
- Dose numbers need a real dose-depth curve for your orbit from SPENVIS. The demo curve is fake.
- The Geant4 program has **not been compiled yet** by its author, so the Part 6 check is how you confirm it works.
- **Next steps:** get the real dimensions, orbit and SPENVIS curve; later, a true particle simulation of the payload.
