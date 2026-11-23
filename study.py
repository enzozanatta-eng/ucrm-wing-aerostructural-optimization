"""uCRM aerostructural wing optimization study with OpenAeroStruct.

Runs: (1) trimmed baseline, (2) optimized design, (3) mesh refinement checks.
Saves results to results/*.json and arrays to results/*.npz.
"""
import json, os, time
import numpy as np
import openmdao.api as om
from ucrm_model import build

os.makedirs("results", exist_ok=True)



def setup(num_y, optimize_design, tol=1e-6, realistic=False):
    prob, surf = build(num_y=num_y)
    m = prob.model
    if realistic:
        # control points run tip -> root: thickness and twist must not decrease toward the root
        m.add_subsystem('mono', om.ExecComp(['dtc = tc[1:] - tc[:-1]', 'dtw = tw[1:] - tw[:-1]'],
                        tc={'val': surf['t_over_c_cp']}, tw={'val': surf['twist_cp'], 'units': 'deg'}, dtc={'shape': 3}, dtw={'shape': 3, 'units': 'deg'}))
        m.connect('wing.geometry.t_over_c_cp', 'mono.tc')
        m.connect('wing.twist_cp', 'mono.tw')
        m.add_constraint('mono.dtc', lower=0.0)
        m.add_constraint('mono.dtw', lower=0.0)
    m.add_objective("AS_point_0.fuelburn", scaler=1e-5)
    m.add_design_var("alpha", lower=-10.0, upper=10.0)
    m.add_design_var("alpha_maneuver", lower=-15.0, upper=15.0)
    m.add_design_var("fuel_mass", lower=0.0, upper=2e5, scaler=1e-5)
    m.add_constraint("AS_point_0.CL", equals=0.5)
    m.add_constraint("AS_point_1.L_equals_W", equals=0.0)
    m.add_constraint("fuel_diff", equals=0.0)
    if optimize_design:
        m.add_design_var("wing.twist_cp", lower=-15.0, upper=15.0, scaler=0.1)
        m.add_design_var("wing.spar_thickness_cp", lower=0.003, upper=0.1, scaler=1e2)
        m.add_design_var("wing.skin_thickness_cp", lower=0.003, upper=0.1, scaler=1e2)
        m.add_design_var("wing.geometry.t_over_c_cp", lower=0.07, upper=0.2, scaler=10.0)
        m.add_constraint("AS_point_1.wing_perf.failure", upper=0.0)
        m.add_constraint("fuel_vol_delta.fuel_vol_delta", lower=0.0)
    prob.driver = om.ScipyOptimizeDriver(optimizer="SLSQP", tol=tol, maxiter=300, disp=False)
    prob.setup()
    for p in ("AS_point_0", "AS_point_1"):
        getattr(prob.model, p).coupled.linear_solver = om.LinearBlockGS(iprint=-1, maxiter=60, use_aitken=True)
        getattr(prob.model, p).coupled.nonlinear_solver.options["iprint"] = -1
    return prob, surf


def g(prob, k):
    v = np.asarray(prob.get_val(k)).real
    return v


def extract(prob, surf):
    r = {}
    for k in ["AS_point_0.fuelburn", "AS_point_0.CL", "AS_point_0.CD", "AS_point_0.wing_perf.CDi",
              "AS_point_0.wing_perf.CDv", "AS_point_0.wing_perf.CDw", "AS_point_1.CL",
              "wing.structural_mass", "AS_point_1.wing_perf.failure", "fuel_vol_delta.fuel_vol_delta",
              "alpha", "alpha_maneuver", "fuel_mass", "AS_point_0.coupled.wing.S_ref"]:
        r[k] = float(np.ravel(g(prob, k))[0])
    for k in ["wing.twist_cp", "wing.spar_thickness_cp", "wing.skin_thickness_cp", "wing.geometry.t_over_c_cp"]:
        r[k] = np.ravel(g(prob, k)).tolist()
    r["L_over_D"] = r["AS_point_0.CL"] / r["AS_point_0.CD"]
    r["wingbox_mass_kg"] = r["wing.structural_mass"] / surf["wing_weight_ratio"]
    return r


def arrays(prob):
    a = {}
    for k in ["wing.mesh", "wing.geometry.twist", "wing.t_over_c", "wing.skin_thickness", "wing.spar_thickness",
              "AS_point_0.coupled.aero_states.wing_sec_forces", "AS_point_1.coupled.aero_states.wing_sec_forces",
              "AS_point_0.coupled.wing.def_mesh", "AS_point_1.coupled.wing.def_mesh",
              "AS_point_0.wing_perf.vonmises", "AS_point_1.wing_perf.vonmises",
              "AS_point_0.coupled.wing.widths", "AS_point_1.coupled.wing.widths", "rho", "v"]:
        a[k.replace(".", "__")] = g(prob, k)
    return a


def run(name, num_y, optimize_design, start=None, realistic=False):
    prob, surf = setup(num_y, optimize_design, realistic=realistic)
    if start:
        for k, v in start.items():
            prob.set_val(k, np.array(v))
    t = time.time()
    fail = prob.run_driver()
    r = extract(prob, surf)
    r["num_y"] = num_y
    r["driver_success"] = bool(prob.driver.result.success) if hasattr(prob.driver, "result") else (not fail)
    r["driver_iterations"] = int(prob.driver.iter_count)
    r["wall_time_s"] = time.time() - t
    json.dump(r, open(f"results/{name}.json", "w"), indent=2)
    np.savez(f"results/{name}.npz", **arrays(prob))
    print(f"{name}: fuelburn={r['AS_point_0.fuelburn']:.0f} kg  L/D={r['L_over_D']:.2f}  "
          f"wingbox={r['wingbox_mass_kg']:.0f} kg  failure={r['AS_point_1.wing_perf.failure']:.3f}  "
          f"iters={r['driver_iterations']}  ok={r['driver_success']}")
    return r


DESIGN_KEYS = ["wing.twist_cp", "wing.spar_thickness_cp", "wing.skin_thickness_cp", "wing.geometry.t_over_c_cp",
               "alpha", "alpha_maneuver", "fuel_mass"]


def start_from(r):
    return {k: r[k] for k in DESIGN_KEYS}


if __name__ == "__main__":
    # 1. baseline (initial uCRM design, trimmed only) at three meshes
    for ny in (15, 21, 31):
        run(f"baseline_ny{ny}", ny, False)
    # 2. free optimization from the baseline start, three meshes
    for ny in (15, 21, 31):
        run(f"optimized_ny{ny}", ny, True)
    # 3. realistic optimization: monotonic t/c and twist from tip to root
    real = run("realistic_ny31", 31, True, realistic=True)
    # 4. free optimization restarted from the realistic optimum (multistart check)
    run("free_restart_ny31", 31, True, start=start_from(real))
    # 5. mesh study: realistic design held fixed, both flight points retrimmed
    for ny in (15, 21, 31, 41, 61):
        run(f"meshstudy_realistic_ny{ny}", ny, False, start=start_from(real))
