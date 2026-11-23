"""Independent checks and figures for the uCRM study."""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib import cm, colors

os.makedirs("figures", exist_ok=True)
R = lambda n: json.load(open(f"results/{n}.json"))
A = lambda n: np.load(f"results/{n}.npz")
ALLOW = 420e6 / 1.5  # yield / safety factor [Pa]
CT, RANGE = 0.53 / 3600, 14.307e6
W0_FIXED = 128000 + 15000 + 2 * 10000  # payload+empty (OAS W0) + reserve + 2 engines [kg]

plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 9.5, "axes.grid": True, "grid.alpha": 0.35,
                     "grid.linestyle": ":", "figure.dpi": 150, "axes.edgecolor": "black", "axes.linewidth": 0.8,
                     "legend.frameon": True, "legend.framealpha": 1.0, "legend.edgecolor": "0.6", "legend.fancybox": False,
                     "axes.titlesize": 10.5, "axes.titleweight": "bold", "xtick.direction": "in", "ytick.direction": "in",
                     "xtick.top": True, "ytick.right": True})
C = {"base": "black", "free": "#c62828", "real": "#1565c0", "ell": "0.45"}


def spanwise_lift(name, point=0):
    a = A(name)
    f = a[f"AS_point_{point}__coupled__aero_states__wing_sec_forces"].sum(axis=0)  # (ny-1,3)
    mesh = a[f"AS_point_{point}__coupled__wing__def_mesh"]
    le = mesh[0]
    ymid = 0.5 * (le[1:, 1] + le[:-1, 1])
    width = np.abs(np.diff(le[:, 1]))
    r = R(name)
    al = np.radians(r["alpha"] if point == 0 else r["alpha_maneuver"])
    L = f[:, 2] * np.cos(al) - f[:, 0] * np.sin(al)
    return np.abs(ymid), L / width, L.sum(), abs(le[0, 1])


def oswald_trefftz(name):
    """Fit Gamma(theta) = sum A_n sin(n theta), odd n, to the computed span loading; e = 1/(1+delta)."""
    y, l, Ltot, s = spanwise_lift(name)
    theta = np.arccos(y / s)
    n = np.array([1, 3, 5, 7])
    M = np.sin(np.outer(theta, n))
    An, *_ = np.linalg.lstsq(M, l, rcond=None)
    delta = np.sum(n[1:] * (An[1:] / An[0]) ** 2)
    return 1.0 / (1.0 + delta)


def nearfield_e(name):
    r = R(name)
    a = A(name)
    s = abs(a["wing__mesh"][0, 0, 1])
    S = r["AS_point_0.coupled.wing.S_ref"]
    AR = (2 * s) ** 2 / S
    return r["AS_point_0.CL"] ** 2 / (np.pi * AR * r["AS_point_0.wing_perf.CDi"]), AR


def breguet(name):
    r = R(name)
    a = A(name)
    V = a["v"][0]
    W_end = W0_FIXED + r["wing.structural_mass"]
    return W_end * (np.exp(RANGE * CT / (V * r["L_over_D"])) - 1.0)


cases = {"Baseline (uCRM initial)": "baseline_ny31", "Free optimum": "free_restart_ny31",
         "Realistic optimum": "realistic_ny31"}
checks = {}
for lab, n in cases.items():
    r = R(n)
    a = A(n)
    vm = a["AS_point_1__wing_perf__vonmises"].max()
    e_nf, AR = nearfield_e(n)
    checks[lab] = dict(fuelburn=r["AS_point_0.fuelburn"], LD=r["L_over_D"], wingbox=r["wingbox_mass_kg"],
                       vm_max_MPa=vm / 1e6, util=vm / ALLOW, fuel_vol_margin=r["fuel_vol_delta.fuel_vol_delta"],
                       CDi=r["AS_point_0.wing_perf.CDi"], CDv=r["AS_point_0.wing_perf.CDv"],
                       CDw=r["AS_point_0.wing_perf.CDw"], CD=r["AS_point_0.CD"], AR=AR,
                       e_nearfield=e_nf, e_trefftz=oswald_trefftz(n), breguet=breguet(n),
                       twist=r["wing.twist_cp"], tc=r["wing.geometry.t_over_c_cp"])
ms = {ny: R(f"meshstudy_realistic_ny{ny}") for ny in [15, 21, 31, 41, 61]}
ms_vm = {ny: A(f"meshstudy_realistic_ny{ny}")["AS_point_1__wing_perf__vonmises"].max() / 1e6 for ny in ms}
# Richardson extrapolation with panels N = (ny-1)/2 = 10, 15, 30 is not a constant ratio; use 15, 20, 30 fit
N = np.array([15, 20, 30.0]); F = np.array([ms[31]["AS_point_0.fuelburn"], ms[41]["AS_point_0.fuelburn"], ms[61]["AS_point_0.fuelburn"]])
from scipy.optimize import brentq
def resid(p):
    c = (F[1] - F[0]) / (N[1] ** -p - N[0] ** -p)
    return F[2] - (F[0] + c * (N[2] ** -p - N[0] ** -p))
p = brentq(resid, 0.2, 4.0)
c = (F[1] - F[0]) / (N[1] ** -p - N[0] ** -p)
F_inf = F[0] - c * N[0] ** -p
checks["mesh"] = {"fuelburn": {ny: ms[ny]["AS_point_0.fuelburn"] for ny in ms}, "vm_max_MPa": ms_vm,
                  "order_p": p, "F_extrapolated": F_inf, "err_ny31_pct": 100 * (F[0] - F_inf) / F_inf,
                  "err_ny61_pct": 100 * (F[2] - F_inf) / F_inf}
json.dump(checks, open("results/checks.json", "w"), indent=2, default=float)
for k, v in checks.items():
    print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()})

# ---------------- Figure 2: span loading ----------------
fig, ax = plt.subplots(figsize=(7.5, 4.2))
for lab, n, col, mk in [("Baseline", "baseline_ny31", C["base"], "s"), ("Free optimum", "free_restart_ny31", C["free"], "^"),
                    ("Realistic optimum", "realistic_ny31", C["real"], "o")]:
    y, l, Lt, s = spanwise_lift(n)
    ax.plot(y / s, l / 1e3, "-", marker=mk, ms=3.5, mfc="white", color=col, label=f"{lab}  (e Trefftz = {oswald_trefftz(n):.3f})")
y, l, Lt, s = spanwise_lift("realistic_ny31")
yy = np.linspace(0, 1, 200); l0 = Lt / (np.pi * s / 4)
ax.plot(yy, l0 * np.sqrt(1 - yy ** 2) / 1e3, "--", color=C["ell"], lw=1.2, label="Elliptic, same total lift")
ax.set_xlabel("Spanwise position  y / (b/2)"); ax.set_ylabel("Lift per unit span  [kN/m]")
ax.set_title("Cruise span loading (Mach 0.85, CL = 0.5)", loc="center"); ax.legend(fontsize=8.5)
plt.tight_layout(); plt.savefig("figures/02_span_loading.png", dpi=200); plt.close()

# ---------------- Figure 3: design variables ----------------
fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
eta = np.linspace(1, 0, 4)
for lab, n, col in [("Baseline", "baseline_ny31", C["base"]), ("Free optimum", "free_restart_ny31", C["free"]),
                    ("Realistic optimum", "realistic_ny31", C["real"])]:
    r = R(n)
    axs[0].plot(eta, r["wing.twist_cp"], "o-", color=col, label=lab)
    axs[1].plot(eta, r["wing.geometry.t_over_c_cp"], "o-", color=col, label=lab)
axs[0].set_title("Twist control points", loc="center"); axs[0].set_ylabel("Twist [deg]")
axs[1].set_title("Thickness to chord control points", loc="center"); axs[1].set_ylabel("t/c")
for ax in axs: ax.set_xlabel("y / (b/2)   (0 = root, 1 = tip)")
axs[1].axhline(0.07, ls=":", color="black", lw=1); axs[1].text(0.02, 0.072, "lower bound 0.07", fontsize=8)
axs[0].annotate("zigzag twist:\nexploits 4 control points", xy=(1/3, R("free_restart_ny31")["wing.twist_cp"][2]),
                xytext=(0.45, 7), fontsize=8, color=C["free"], arrowprops=dict(arrowstyle="->", color=C["free"]))
axs[1].annotate("mid-span thickness bump", xy=(2/3, R("free_restart_ny31")["wing.geometry.t_over_c_cp"][1]),
                xytext=(0.08, 0.135), fontsize=8, color=C["free"], arrowprops=dict(arrowstyle="->", color=C["free"]))
axs[0].legend(fontsize=8)
plt.tight_layout(); plt.savefig("figures/03_design_variables.png", dpi=200); plt.close()

# ---------------- Figure 4: stress utilization ----------------
fig, ax = plt.subplots(figsize=(7.5, 3.8))
for lab, n, col in [("Baseline", "baseline_ny31", C["base"]), ("Free optimum", "free_restart_ny31", C["free"]),
                    ("Realistic optimum", "realistic_ny31", C["real"])]:
    a = A(n); le = a["AS_point_1__coupled__wing__def_mesh"][0]; s = abs(le[0, 1])
    ymid = np.abs(0.5 * (le[1:, 1] + le[:-1, 1])) / s
    ax.plot(ymid, a["AS_point_1__wing_perf__vonmises"].max(axis=1) / ALLOW, "o-", ms=3, color=col, label=lab)
ax.axhline(1.0, color="black", lw=1.2); ax.text(0.62, 1.02, "allowable = yield / 1.5 = 280 MPa", fontsize=8)
ax.fill_between([0, 1], 1.0, 1.35, color="#c62828", alpha=0.06)
ax.set_xlim(0, 1); ax.set_xlabel("y / (b/2)"); ax.set_ylabel("von Mises / allowable")
ax.set_title("Wingbox stress at the 2.5 g maneuver", loc="center"); ax.legend(fontsize=8.5)
plt.tight_layout(); plt.savefig("figures/04_stress_utilization.png", dpi=200); plt.close()

# ---------------- Figure 5: mesh study ----------------
fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
Ns = np.array([(ny - 1) / 2 for ny in ms]); Fs = np.array([ms[ny]["AS_point_0.fuelburn"] for ny in ms]) / 1e3
ax[0].plot(Ns, Fs, "o-", color=C["real"]); ax[0].axhline(F_inf / 1e3, ls="--", color="black", lw=1)
ax[0].text(Ns[0], F_inf / 1e3 + 0.05, f"Richardson extrapolation {F_inf/1e3:.2f} t (order {p:.2f})", fontsize=8)
ax[0].set_xlabel("Spanwise panels on the half wing"); ax[0].set_ylabel("Fuel burn [t]")
ax[0].set_title("Fuel burn vs mesh, fixed realistic design", loc="center")
ax[1].plot(Ns, list(ms_vm.values()), "o-", color=C["free"]); ax[1].axhline(280, color="black", lw=1.2)
ax[1].set_xlabel("Spanwise panels on the half wing"); ax[1].set_ylabel("Peak von Mises at 2.5 g [MPa]")
ax[1].set_title("Peak stress vs mesh", loc="center")
plt.tight_layout(); plt.savefig("figures/05_mesh_study.png", dpi=200); plt.close()

# ---------------- Figure 6: summary bars ----------------
labs = list(cases.keys())
fig, ax = plt.subplots(1, 3, figsize=(11, 3.4))
cols = [C["base"], C["free"], C["real"]]
for i, (key, t, sc) in enumerate([("fuelburn", "Fuel burn [t]", 1e-3), ("LD", "Cruise L/D", 1), ("wingbox", "Wingbox mass [t]", 1e-3)]):
    vals = [checks[l][key] * sc for l in labs]
    ax[i].bar(range(3), vals, color=cols); ax[i].set_xticks(range(3)); ax[i].set_xticklabels(["Baseline", "Free", "Realistic"])
    ax[i].set_title(t, loc="center"); lo = min(vals) * 0.9; ax[i].set_ylim(lo, max(vals) * 1.03)
    for k, v in enumerate(vals): ax[i].text(k, v, f"{v:.2f}" if key == "LD" else f"{v:.1f}", ha="center", va="bottom", fontsize=9)
plt.tight_layout(); plt.savefig("figures/06_summary.png", dpi=200); plt.close()
print("figures done")

# ---------------- Figure 7: deflected shapes, front view ----------------
a = A("realistic_ny31")
fig, ax = plt.subplots(figsize=(8, 3.0))
for key, lab, col, ls in [("wing__mesh", "Jig shape", "0.5", "--"),
                          ("AS_point_0__coupled__wing__def_mesh", "Cruise, n = 1.0", C["real"], "-"),
                          ("AS_point_1__coupled__wing__def_mesh", "Maneuver, n = 2.5", C["free"], "-")]:
    m = a[key]; y = np.abs(m[0, :, 1]); z = m[0, :, 2] - a["wing__mesh"][0, -1, 2]
    ax.plot(y, z, ls, color=col, lw=1.6, label=f"{lab}   (tip {z[0]:+.2f} m)")
ax.set_aspect("equal"); ax.set_xlim(0, 30); ax.set_ylim(-0.5, 5)
ax.set_xlabel("Spanwise coordinate y [m]"); ax.set_ylabel("Vertical displacement\nof leading edge [m]")
ax.set_title("Leading edge vertical position, realistic optimum (equal axis scale)")
ax.legend(loc="upper left", fontsize=8.5)
plt.tight_layout(); plt.savefig("figures/07_front_view_deflection.png", dpi=200); plt.close()
print("fig7 done")
