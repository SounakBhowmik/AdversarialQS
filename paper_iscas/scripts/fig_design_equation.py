"""Fig. 2: closed-form fallback harm vs spoof size, with frozen-run observations.

Input: data/theory_predictions.csv (written by analysis/project1/reference_theory.py from the
frozen run). Reimplements that script's fallback_harm() exactly; nothing is fitted here.
Output: figures/design_equation.pdf, sized for one IEEE column with print-legible fonts.
"""

import csv
from pathlib import Path
from statistics import NormalDist

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent.parent
H = 25.0  # harm tolerance, nT (strictly greater is harmful)
PHI = NormalDist().cdf


def mass(lo, hi, sigma):
    """P(lo <= eps <= hi) for eps ~ N(0, sigma^2); empty intervals give zero."""
    return max(PHI(hi / sigma) - PHI(min(lo, hi) / sigma), 0.0)


def fallback_harm(d, sigma, kappa, shift=0.0, h=H):
    """Same as reference_theory.fallback_harm (independent reference when shift = 0)."""
    lo, hi = d - shift - kappa, d - shift + kappa
    accept = mass(lo, hi, sigma)
    accurate_accept = mass(max(lo, -h - shift), min(hi, h - shift), sigma)
    reference_harm = 1 - mass(-h - shift, h - shift, sigma)
    return (accept if d > h else 0.0) + reference_harm - (accept - accurate_accept)


rows = {r["case"]: r for r in csv.DictReader(open(HERE / "data/theory_predictions.csv"))}
curves = [  # (case used for the calibrated kappa, sigma_R, color)
    ("reference_noise_15nT", 15, "#2a78d6"),
    ("time_frequency", 20, "#eb6834"),
    ("reference_noise_50nT", 50, "#1baf7a"),
]
points = ["reference_noise_15nT", "time_frequency", "reference_noise_50nT", "frequency_50nT"]

plt.rcParams.update({"font.size": 8, "pdf.fonttype": 42, "axes.spines.top": False,
                     "axes.spines.right": False})
fig, ax = plt.subplots(figsize=(3.5, 2.1), layout="constrained")
grid = np.linspace(25.5, 170, 700)
color_of = {}
for case, sigma, color in curves:
    kappa = float(rows[case]["kappa_median_nT"])
    color_of[sigma] = color
    ax.plot(grid, [100 * fallback_harm(d, sigma, kappa) for d in grid], color=color, lw=1.8)
    floor = 100 * (1 - mass(-H, H, sigma))
    ax.hlines(floor, 25, 170, color=color, lw=1.0, ls=(0, (3, 2)))
    ax.annotate(rf"$\sigma_R$ = {sigma} nT", (170, 100 * fallback_harm(170, sigma, kappa)),
                xytext=(4, 0), textcoords="offset points", va="center", fontsize=8, color=color)
kappa20 = float(rows["time_frequency"]["kappa_median_nT"])
ax.axvspan(H, kappa20 - H, color="#eb6834", alpha=0.18, lw=0)
ax.annotate("blind window\n($\\sigma_R$ = 20 nT)", xy=((H + kappa20 - H) / 2, 52),
            xytext=(80, 52), textcoords="data", fontsize=7.5, va="center",
            arrowprops=dict(arrowstyle="->", lw=0.8, color="#52514e"), color="#52514e")
for case in points:
    r = rows[case]
    obs, lo, hi = (100 * float(r[k]) for k in
                   ("observed_fallback", "observed_fallback_low", "observed_fallback_high"))
    color = color_of[int(round(float(r["sigma_nT"])))]
    ax.errorbar(float(r["spoof_nT"]), obs, yerr=[[obs - lo], [hi - obs]], fmt="o", ms=5.5,
                mfc="white", mec=color, mew=1.5, ecolor=color, zorder=5)
ax.set(xlim=(20, 200), ylim=(-3, 105), xlabel="Spoof size $d$ (nT)",
       ylabel="Harmful releases (%)")
ax.set_xticks([25, 50, 75, 100, 125, 150])
fig.savefig(HERE / "figures/design_equation.pdf")
print("wrote figures/design_equation.pdf")
