#!/usr/bin/env python3
"""
cubesat_model.py - a fill-in-the-blanks CubeSat radiation-shielding model.

WHAT IT DOES
  Takes the satellite you describe in a config file (walls, solar panels, circuit
  boards, payload boxes...) and, for every point you care about, asks:
  "looking out in 1800 directions, how much material is between me and space?"
  That is the method of Seo et al. (2012). If you also give it a dose-depth curve
  for your orbit (from SPENVIS), it turns shielding into a total ionizing dose
  and compares it with what your electronics can tolerate.

HOW TO RUN
  python cubesat_model.py config_12U.json
  python cubesat_model.py config_6U.json  --out results_6U
  python cubesat_model.py config_12U.json --demo            # pipeline demo, FAKE dose numbers
  python cubesat_model.py config_12U.json --sweep payload --values 1 2 3 5
        (what happens to the payload if its wall is 1, 2, 3 or 5 mm thick?)

IMPORTANT
  * Shielding numbers are only as good as the dimensions in your config.
  * Dose numbers are only real if the dose-depth curve is real (from SPENVIS).
  * This is a screening tool for total ionizing dose, not a full Geant4 simulation,
    and it says nothing about single-event effects.
"""
import argparse
import copy
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Densities in g/cm3. Shielding is converted to "millimeters of aluminum
# equivalent" by scaling with density relative to aluminum (the paper's method).
DENSITY = {"Al": 2.699, "Cu": 8.96, "Ti": 4.51, "Steel": 8.0, "Ta": 16.65,
           "W": 19.3, "Pb": 11.35, "Si": 2.33, "FR4": 1.85, "PE": 0.94}


# ----------------------------------------------------------------------------
# 1. Build the satellite from the config
# ----------------------------------------------------------------------------
def build_model(cfg):
    """Returns (solids, points, warnings).
    solids : list of boxes. A hollow box is a big box (+) minus a smaller box (-).
    points : list of (name, xyz) where we measure shielding."""
    solids, points, warns = [], [], []

    def add_box(center, size, mat, sign=1):
        if mat not in DENSITY:
            raise ValueError(f"Unknown material '{mat}'. Choose from {sorted(DENSITY)}")
        solids.append({"c": np.array(center, float), "h": np.array(size, float) / 2,
                       "mat": mat, "sign": sign})

    def add_hollow(center, size, wall, mat, label):
        add_box(center, size, mat, +1)
        inner = [s - 2 * wall for s in size]
        if min(inner) <= 0:
            warns.append(f"{label}: wall of {wall} mm is too thick for its size, treated as solid.")
            return
        add_box(center, inner, mat, -1)

    sat = cfg["satellite"]
    Lx, Ly, Lz = sat["outer_mm"]
    wall, wmat = sat["wall_mm"], sat.get("wall_material", "Al")
    add_hollow([0, 0, 0], [Lx, Ly, Lz], wall, wmat, "structure")

    sp = cfg.get("solar_panels", {})
    if sp.get("enabled", False):
        t, m = sp["thickness_mm"], sp.get("material", "Si")
        add_box([(Lx + t) / 2, 0, 0], [t, Ly, Lz], m); add_box([-(Lx + t) / 2, 0, 0], [t, Ly, Lz], m)
        add_box([0, (Ly + t) / 2, 0], [Lx, t, Lz], m); add_box([0, -(Ly + t) / 2, 0], [Lx, t, Lz], m)
        add_box([0, 0, (Lz + t) / 2], [Lx, Ly, t], m); add_box([0, 0, -(Lz + t) / 2], [Lx, Ly, t], m)

    # Circuit boards: stacked along z. A point sits 1 mm above each board's surface.
    b = cfg.get("boards", {})
    z_top_stack = -Lz / 2 + wall
    for i in range(int(b.get("count", 0))):
        bx, by = b["size_mm"]
        z = -Lz / 2 + wall + b.get("start_above_floor_mm", 20) + i * b["pitch_mm"]
        add_box([0, 0, z], [bx, by, b["thickness_mm"]], b.get("material", "FR4"))
        points.append((f"board{i + 1}", np.array([0, 0, z + b["thickness_mm"] / 2 + 1.0])))
        z_top_stack = z + b["thickness_mm"] / 2
        if bx > Lx - 2 * wall or by > Ly - 2 * wall:
            warns.append(f"board{i + 1} ({bx} x {by} mm) does not fit inside the walls.")

    # Components (payload boxes, etc.)
    for comp in cfg.get("components", []):
        size = comp["size_mm"]
        c = comp.get("center_mm", "above_stack")
        if c == "above_stack":
            c = [0, 0, z_top_stack + comp.get("gap_above_stack_mm", 15) + size[2] / 2]
        mat = comp.get("material", "Al")
        if comp.get("wall_mm") is None:
            add_box(c, size, mat)
        else:
            add_hollow(c, size, comp["wall_mm"], mat, comp["name"])
        if comp.get("add_point", True):
            points.append((comp["name"], np.array(c, float)))
        if c[2] + size[2] / 2 > Lz / 2 - wall:
            warns.append(f"{comp['name']} sticks out through the top of the satellite.")
        if c[2] - size[2] / 2 < z_top_stack and cfg.get("boards", {}).get("count", 0) > 0:
            warns.append(f"{comp['name']} overlaps the board stack.")
        if size[0] > Lx - 2 * wall or size[1] > Ly - 2 * wall:
            warns.append(f"{comp['name']} is wider than the interior.")

    for p in cfg.get("extra_points", []):
        points.append((p["name"], np.array(p["xyz_mm"], float)))
    return solids, points, warns


# ----------------------------------------------------------------------------
# 2. Shine rays in every direction and add up the material they cross
# ----------------------------------------------------------------------------
def make_sky(n_cos, n_phi):
    """Equal-solid-angle grid over the whole sky (uniform in cos(theta) and phi)."""
    k = np.arange(n_cos * n_phi)
    ic, jp = np.divmod(k, n_phi)
    ct = -1 + 2 * (ic + 0.5) / n_cos
    st = np.sqrt(1 - ct ** 2)
    ph = 2 * np.pi * (jp + 0.5) / n_phi
    return np.stack([st * np.cos(ph), st * np.sin(ph), ct], axis=1), ic, jp


def thickness_from(p, D, solids):
    """Aluminum-equivalent thickness (mm) along each direction in D, starting at p."""
    D = np.where(np.abs(D) < 1e-12, 1e-12, D)
    total = np.zeros(len(D))
    for s in solids:
        lo, hi = s["c"] - s["h"], s["c"] + s["h"]
        t1, t2 = (lo - p) / D, (hi - p) / D
        t_in = np.minimum(t1, t2).max(axis=1)       # ray enters the box
        t_out = np.maximum(t1, t2).min(axis=1)      # ray leaves the box
        length = np.clip(t_out - np.maximum(t_in, 0), 0, None)
        total += s["sign"] * length * DENSITY[s["mat"]] / DENSITY["Al"]
    return np.clip(total, 0, None)


# ----------------------------------------------------------------------------
# 3. Dose-depth curve -> dose
# ----------------------------------------------------------------------------
def load_curve(path):
    arr = np.loadtxt(path, delimiter=",", comments="#")
    t, d = arr[:, 0], arr[:, 1]
    order = np.argsort(t)
    t, d = t[order], d[order]
    keep = d > 0
    t, d = t[keep], d[keep]
    # Interpolate log(dose): dose falls roughly exponentially with thickness.
    return lambda x: np.exp(np.interp(x, t, np.log(d)))


def demo_curve_file(out_dir):
    """FAKE curve, only so you can see the pipeline work end to end."""
    t = np.array([0.1, 0.5, 1, 2, 3, 5, 8, 10, 15, 20])
    d = 50 * np.exp(-t / 2.5) + 2 * np.exp(-t / 12)
    path = Path(out_dir) / "demo_dose_depth_NOT_REAL.csv"
    np.savetxt(path, np.c_[t, d], delimiter=",", fmt="%.4f",
               header="DEMO ONLY - NOT REAL DATA. columns: thickness_mm_Al, dose_krad_per_year")
    return str(path)


# ----------------------------------------------------------------------------
# 4. Run everything for one config
# ----------------------------------------------------------------------------
def run(cfg, curve_path=None):
    solids, points, warns = build_model(cfg)
    g = cfg.get("sky_grid", {})
    n_cos, n_phi = g.get("n_cos", 30), g.get("n_phi", 60)
    D, ic, jp = make_sky(n_cos, n_phi)
    w = 1.0 / len(D)                                   # every sector has equal solid angle
    F = load_curve(curve_path) if curve_path else None
    m = cfg.get("mission", {})
    years = m.get("duration_years", 1.0)
    curve_years = cfg.get("dose_curve", {}).get("curve_covers_years", 1.0)

    rays, rows = [], []
    for name, p in points:
        t = thickness_from(p, D, solids)
        rays.append(pd.DataFrame({"point": name, "sector": np.arange(len(D)), "ic": ic, "jp": jp,
                                  "Al_equiv_mm": t}))
        row = {"point": name, "min_mm": t.min(), "median_mm": np.median(t),
               "pct_sky_under_10mm": 100 * w * np.sum(t < 10)}
        if F is not None:
            tot = np.sum(F(t)) * w * years / curve_years
            tol, margin = m.get("part_tolerance_krad", 10.0), m.get("design_margin", 2.0)
            row["mission_dose_krad"] = tot
            row["status"] = "OK" if tot * margin <= tol else "CHECK"
        rows.append(row)
    return pd.concat(rays, ignore_index=True), pd.DataFrame(rows), warns, (n_cos, n_phi)


def plot(rays, summary, cfg, grid, path, demo):
    n_cos, n_phi = grid
    names = list(summary["point"])
    show = list(dict.fromkeys([names[0], names[len(names) // 2], names[-1]]))
    fig = plt.figure(figsize=(14, 9)); gs = fig.add_gridspec(2, 3)
    for k, n in enumerate(show):
        ax = fig.add_subplot(gs[0, k]); g = rays[rays.point == n]
        img = np.full((n_cos, n_phi), np.nan); img[g.ic, g.jp] = g.Al_equiv_mm
        im = ax.imshow(img, origin="lower", aspect="auto", extent=[0, 360, -1, 1],
                       cmap="viridis_r", vmin=0, vmax=40)
        ax.set_title(f"Shielding seen from {n}"); ax.set_xlabel("compass direction (deg)")
        ax.set_ylabel("cos θ   (-1 = down, +1 = up)")
        plt.colorbar(im, ax=ax, label="Al-equivalent (mm), capped at 40")
    ax = fig.add_subplot(gs[1, 0:2]); x = np.arange(len(names))
    ax.bar(x, summary.pct_sky_under_10mm, color="#4c78a8")
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=20); ax.set_ylim(0, 100)
    ax.set_ylabel("% of sky with < 10 mm Al-equivalent")
    ax.set_title("How much of the sky is thinly shielded (higher = more dose)")
    for xi, f in zip(x, summary.pct_sky_under_10mm): ax.text(xi, f + 1, f"{f:.0f}%", ha="center")
    ax = fig.add_subplot(gs[1, 2]); ax.axis("off")
    lines = [f"{'point':<14}{'min':>6}{'median':>8}" + ("  dose(krad)  status" if "status" in summary else "")]
    for _, r in summary.iterrows():
        s = f"{r.point:<14}{r.min_mm:6.2f}{r.median_mm:8.1f}"
        if "status" in summary: s += f"  {r.mission_dose_krad:9.2f}  {r.status}"
        lines.append(s)
    ax.text(0, 0.95, "\n".join(lines), family="monospace", va="top", fontsize=9)
    sat = cfg["satellite"]
    title = f"{sat.get('size_label', '')} CubeSat shielding model   orbit: {cfg.get('mission', {}).get('orbit_label', '?')}"
    if demo: title += "\nDEMO CURVE - DOSE NUMBERS ARE NOT REAL"
    fig.suptitle(title, color="red" if demo else "black")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def print_summary(summary):
    pd.set_option("display.float_format", lambda v: f"{v:.2f}")
    print(summary.to_string(index=False))


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config")
    ap.add_argument("--out", default="model_output")
    ap.add_argument("--demo", action="store_true", help="use a FAKE dose curve to demonstrate the pipeline")
    ap.add_argument("--sweep", metavar="COMPONENT", help="name of a component whose wall thickness to vary")
    ap.add_argument("--values", type=float, nargs="+", help="wall thicknesses (mm) for --sweep")
    a = ap.parse_args()

    cfg = json.load(open(a.config))
    out = Path(a.out); out.mkdir(exist_ok=True)
    curve = cfg.get("dose_curve", {}).get("csv")
    if a.demo:
        curve = demo_curve_file(out)
        print("*** DEMO MODE: the dose curve is FAKE. Dose numbers below are NOT real. ***\n")
    elif curve:
        curve = str(Path(a.config).parent / curve)

    if a.sweep:
        if not a.values: ap.error("--sweep needs --values, e.g. --values 1 2 3 5")
        print(f"Sweep: wall thickness of '{a.sweep}' (point = its center)\n")
        rows = []
        for v in a.values:
            c2 = copy.deepcopy(cfg)
            hit = [c for c in c2["components"] if c["name"] == a.sweep]
            if not hit: ap.error(f"no component named '{a.sweep}' in the config")
            hit[0]["wall_mm"] = v
            _, summ, _, _ = run(c2, curve)
            r = summ[summ.point == a.sweep].iloc[0].to_dict(); r["wall_mm"] = v; rows.append(r)
        df = pd.DataFrame(rows); cols = ["wall_mm", "min_mm", "median_mm", "pct_sky_under_10mm"]
        if "mission_dose_krad" in df: cols += ["mission_dose_krad", "status"]
        print_summary(df[cols]); df[cols].to_csv(out / "sweep.csv", index=False)
        return

    rays, summary, warns, grid = run(cfg, curve)
    for w in warns: print("WARNING:", w)
    if warns: print()
    print_summary(summary)
    rays[["point", "sector", "Al_equiv_mm"]].to_csv(out / "rays.csv", index=False)
    summary.to_csv(out / "summary.csv", index=False)
    plot(rays, summary, cfg, grid, out / "shielding.png", a.demo)
    if curve is None:
        print("\nNo dose curve given, so this is shielding only. To get dose, export a dose-depth"
              "\ncurve for your orbit from SPENVIS and put its file name in the config (dose_curve > csv).")
    print(f"\nFiles written to {out}/")


if __name__ == "__main__":
    main()
