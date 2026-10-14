"""
tid.py - combine the Geant4 shielding rays with a dose-depth curve.

Implements Eq. 1 of Seo et al. (2012):

    TID = sum_i  F(t_i) * dOmega_i / (4*pi)

  t_i       aluminum-equivalent shielding thickness of sky sector i (from shield.cc)
  F(t)      dose from the SPENVIS/SHIELDOSE-2 dose-depth curve at thickness t
  dOmega_i  solid angle of sector i

Usage:
    python tid.py rays.csv dose_depth.csv

dose_depth.csv: two columns, no header needed (lines starting with # are skipped)
    thickness_mm_Al, dose        (dose in whatever unit you exported, e.g. krad/year)
The output is in the same dose unit as your curve.
"""
import sys

import numpy as np
import pandas as pd


def main(rays_file, curve_file):
    rays = pd.read_csv(rays_file)
    curve = np.loadtxt(curve_file, delimiter=",", comments="#")
    t_curve, d_curve = curve[:, 0], curve[:, 1]

    # Dose falls off roughly exponentially with thickness, so interpolate
    # log(dose) linearly. Outside the curve's range the end values are used.
    order = np.argsort(t_curve)
    t_curve, d_curve = t_curve[order], d_curve[order]
    keep = d_curve > 0
    t_curve, d_curve = t_curve[keep], d_curve[keep]

    def F(t):
        return np.exp(np.interp(t, t_curve, np.log(d_curve)))

    print(f"Curve covers {t_curve.min():g} to {t_curve.max():g} mm Al "
          f"(thicknesses outside this range use the nearest end value)\n")
    print(f"{'point':<16}{'TID':>12}{'min t (mm)':>12}{'median t':>10}{'% sky <10mm':>13}")

    for name, grp in rays.groupby("point", sort=False):
        t = grp["Al_equiv_mm"].to_numpy()
        w = grp["dOmega_sr"].to_numpy() / (4 * np.pi)   # fraction of the sky per sector
        tid = np.sum(F(t) * w)
        frac_thin = 100 * np.sum(w[t < 10.0])
        print(f"{name:<16}{tid:>12.4g}{t.min():>12.3f}{np.median(t):>10.2f}{frac_thin:>13.1f}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
