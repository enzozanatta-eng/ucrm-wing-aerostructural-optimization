"""Photoreal-style renders of the optimized uCRM wing with PyVista (VTK, off-screen).

The wing surface is built from the OpenAeroStruct leading/trailing edges (jig and deflected),
the optimized t/c distribution and a representative airfoil shape (visualization only).
Colors are the computed wingbox stress utilization at the 2.5 g maneuver.
"""
import json
import numpy as np
import pyvista as pv
from scipy.interpolate import CubicSpline

pv.OFF_SCREEN = True
ALLOW = 280e6
NAME = "realistic_ny31"
a = np.load(f"results/{NAME}.npz")
chk = json.load(open("results/checks.json"))

jig = a["wing__mesh"]
cru = a["AS_point_0__coupled__wing__def_mesh"]
man = a["AS_point_1__coupled__wing__def_mesh"]
ny = jig.shape[1]
tc_el = a["wing__t_over_c"][0]
ut_el = a["AS_point_1__wing_perf__vonmises"].max(axis=1) / ALLOW
node = np.arange(ny)
tc_n = np.interp(node, node[:-1] + 0.5, tc_el)
ut_n = np.interp(node, node[:-1] + 0.5, ut_el)

NS, NC = 240, 90
sn = np.linspace(0, 1, ny)
ss = np.linspace(0, 1, NS)
xc = (1 - np.cos(np.linspace(0, np.pi, NC))) / 2
thick = 5 * (0.2969 * np.sqrt(xc) - 0.1260 * xc - 0.3516 * xc ** 2 + 0.2843 * xc ** 3 - 0.1036 * xc ** 4)
camber = 0.018 * np.sin(np.pi * xc) ** 1.5 * (1 - 0.6 * xc)  # mild aft-loaded camber, visual only


def spl(v):
    return CubicSpline(sn, v, bc_type="natural")(ss)


def camber_full(xs):
    return np.interp(xs, xc, camber)


def section_points(mesh, mirror=False, offset=np.zeros(3)):
    """Rebuild the surface cleanly: z = camber*c + t/c * c * thickness/2."""
    le = np.stack([spl(mesh[0, :, k]) for k in range(3)], 1)
    te = np.stack([spl(mesh[-1, :, k]) for k in range(3)], 1)
    tc = np.interp(ss, sn, tc_n)
    ut = np.interp(ss, sn, ut_n)
    cv = te - le
    c = np.linalg.norm(cv, axis=1)
    xs = np.concatenate([xc[::-1], xc[1:]])
    half = np.concatenate([(0.5 * thick)[::-1], -(0.5 * thick)[1:]])
    cam = camber_full(xs)
    P = le[:, None, :] + cv[:, None, :] * xs[None, :, None]
    P[..., 2] += c[:, None] * cam[None, :] + (c * tc)[:, None] * half[None, :]
    if mirror:
        P[..., 1] *= -1
    P += offset
    g = pv.StructuredGrid(P[..., 0], P[..., 1], P[..., 2])
    g["util"] = np.repeat(ut[:, None], P.shape[1], 1).ravel(order="F")
    return g


def fuselage(x0=3.0, x1=63.0, r=2.95, zc=5.6):
    xs = np.linspace(x0, x1, 160)
    t = (xs - x0) / (x1 - x0)
    tn = np.clip(t / 0.13, 0, 1)
    nose = np.sqrt(1 - (1 - tn) ** 2)
    tail = np.clip((1 - t) / 0.30, 0, 1) ** 0.75
    tail = 0.12 + 0.88 * tail
    rad = r * np.minimum(nose, tail)
    zoff = np.where(t > 0.72, (t - 0.72) / 0.28 * 1.6, 0.0)
    th = np.linspace(0, 2 * np.pi, 72)
    X = xs[:, None] * np.ones_like(th)
    Y = rad[:, None] * np.cos(th)
    Z = zc + zoff[:, None] + rad[:, None] * np.sin(th)
    return pv.StructuredGrid(X, Y, Z)


def tail_surface(root_le, root_c, tip_le, tip_c, tc=0.10, vertical=False):
    xs = np.concatenate([xc[::-1], xc[1:]])
    half = np.concatenate([(0.5 * thick)[::-1], -(0.5 * thick)[1:]])
    pts = []
    for le, c in [(root_le, root_c), (tip_le, tip_c)]:
        le = np.array(le, float)
        p = np.zeros((xs.size, 3))
        p[:, 0] = le[0] + c * xs
        if vertical:
            p[:, 1] = le[1] + c * tc * half
            p[:, 2] = le[2]
        else:
            p[:, 1] = le[1]
            p[:, 2] = le[2] + c * tc * half
        pts.append(p)
    P = np.stack(pts, 0)
    return pv.StructuredGrid(P[..., 0], P[..., 1], P[..., 2])


def aircraft_context():
    parts = [fuselage()]
    for s in (1, -1):
        parts.append(tail_surface([54.5, 0.0, 6.0], 7.2, [59.5, 10.5 * s, 6.8], 2.8))
    parts.append(tail_surface([53.0, 0.0, 6.6], 9.0, [60.5, 0.0, 16.5], 3.6, vertical=True))
    return parts


def base_plotter(size=(2600, 1500)):
    p = pv.Plotter(off_screen=True, window_size=size, lighting="none")
    p.set_background("white")
    p.enable_lightkit()
    p.enable_anti_aliasing("ssaa")
    return p


SBAR = dict(title="von Mises / allowable [-]\n", color="black", title_font_size=24, label_font_size=22,
            n_labels=11, fmt="%.1f", vertical=True, position_x=0.88, position_y=0.20, height=0.6, width=0.035,
            font_family="arial")


def hero(path):
    p = base_plotter()
    for m in (False, True):
        act = p.add_mesh(section_points(man, m), scalars="util", cmap="jet", clim=(0, 1), n_colors=10,
                         smooth_shading=False, show_scalar_bar=False)
        g = section_points(jig, m)
        p.add_mesh(g.extract_feature_edges(boundary_edges=True, feature_edges=False, manifold_edges=False,
                                           non_manifold_edges=False), color="black", line_width=1.5)
    for part in aircraft_context():
        p.add_mesh(part, color="#d9d9d9", smooth_shading=True, opacity=0.55)
    p.add_scalar_bar(mapper=act.mapper, **SBAR)
    p.camera_position = [(-30, 78, 46), (34, 0, 7.0), (0.32, -0.25, 0.91)]
    p.camera.zoom(1.15)
    p.add_axes(color="black", line_width=3, labels_off=False)
    p.add_text("Deformed shape at n = 2.5 (true scale). Black outline: jig shape.", position="upper_left", font_size=12, color="black")
    p.screenshot(path, transparent_background=False)
    p.close()


def front_view(path):
    """Looking aft: jig, 1 g cruise and 2.5 g shapes."""
    p = base_plotter((2600, 1100))
    for m in (False, True):
        p.add_mesh(section_points(jig, m), color="#9aa3b5", opacity=0.35, smooth_shading=True)
        p.add_mesh(section_points(cru, m), color="#00b4c6", smooth_shading=True, specular=0.5, opacity=0.9)
        p.add_mesh(section_points(man, m), color="#ff6b4a", smooth_shading=True, specular=0.5)
    
    p.camera_position = [(-90, 0, 6.0), (30, 0, 6.0), (0, 0, 1)]
    p.enable_parallel_projection()
    p.camera.parallel_scale = 13.5
    p.screenshot(path)
    p.close()


if __name__ == "__main__":
    hero("figures/01_wing_3d_stress_2p5g.png")
    print("rendered")


def autocrop(path, pad=30):
    from PIL import Image, ImageChops
    im = Image.open(path).convert("RGB")
    bbox = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox()
    l, t, r, b = bbox
    im.crop((max(l - pad, 0), max(t - pad, 0), min(r + pad, im.width), min(b + pad, im.height))).save(path)


if __name__ == "__main__":
    autocrop("figures/01_wing_3d_stress_2p5g.png")
