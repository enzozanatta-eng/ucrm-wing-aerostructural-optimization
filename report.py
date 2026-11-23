"""Build the PDF report from results/checks.json and the figures."""
import json
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

F = "/usr/share/fonts/truetype/liberation/"
pdfmetrics.registerFont(TTFont("C", F + "LiberationSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("CB", F + "LiberationSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("CI", F + "LiberationSans-Italic.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("C", normal="C", bold="CB", italic="CI", boldItalic="CB")

c = json.load(open("results/checks.json"))
B, FR, RE, M = c["Baseline (uCRM initial)"], c["Free optimum"], c["Realistic optimum"], c["mesh"]
free_b = json.load(open("results/optimized_ny31.json"))

ACC = colors.HexColor("#0b3a5b")
H1 = ParagraphStyle("h1", fontName="CB", fontSize=13.5, leading=17, textColor=ACC, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("b", fontName="C", fontSize=10.3, leading=13.8, spaceAfter=5, alignment=4)
CAP = ParagraphStyle("cap", fontName="CI", fontSize=9, leading=11.5, textColor=colors.HexColor("#4a5568"), spaceAfter=8)
SMALL = ParagraphStyle("s", fontName="C", fontSize=9.3, leading=12)
TITLE = ParagraphStyle("t", fontName="CB", fontSize=21, leading=25, textColor=ACC)
SUB = ParagraphStyle("st", fontName="C", fontSize=11.5, leading=15, textColor=colors.HexColor("#4a5568"))

W = A4[0] - 36 * mm


def fig(path, width=W):
    w, h = PILImage.open(path).size
    return Image(path, width=width, height=width * h / w)


def table(rows, widths, head=True):
    t = Table(rows, colWidths=widths)
    st = [("FONT", (0, 0), (-1, -1), "C", 9.4), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACC), ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.grey),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("ALIGN", (1, 0), (-1, -1), "CENTER")]
    if head:
        st.append(("FONT", (0, 0), (-1, 0), "CB", 9.4))
    t.setStyle(TableStyle(st))
    return t


pct = lambda a, b: f"{100 * (a / b - 1):+.1f}%"
s = []
s += [Paragraph("Aerostructural Optimization of the uCRM Wing", TITLE),
      Paragraph("Fuel burn minimization with OpenAeroStruct, an engineering review of the optimum, and independent checks", SUB),
      Spacer(1, 2), Paragraph("Enzo Alves Zanatta, Mechanical Engineer  |  November 2026  |  github.com/enzozanatta-eng", SMALL),
      Spacer(1, 8), fig("figures/01_wing_3d_stress_2p5g.png"),
      Paragraph("Figure 1. Realistic optimum deformed at the 2.5 g maneuver (true scale), colored by wingbox von Mises stress over the 280 MPa allowable. Fuselage, tail and airfoil shape are illustrative only.", CAP), Spacer(1, 6)]

s += [Paragraph("Summary", H1), Paragraph(
    f"A uCRM based transport wing (semi-span 29.4 m, aspect ratio {RE['AR']:.1f}) was optimized for minimum fuel burn over a "
    f"14,307 km mission, with twist, thickness to chord ratio and wingbox spar and skin thickness as design variables, and "
    f"a 2.5 g stress constraint, a fuel volume constraint and lift trim at both flight points. The starting design is not "
    f"feasible: its wingbox reaches {B['vm_max_MPa']:.0f} MPa at 2.5 g against an allowable of 280 MPa, and the required fuel "
    f"does not fit in the wing ({B['fuel_vol_margin']:.1f} m³). The feasible optimum with realism constraints burns "
    f"<b>{RE['fuelburn']/1e3:.1f} t</b> of fuel ({pct(RE['fuelburn'], B['fuelburn'])}), with cruise L/D raised from "
    f"{B['LD']:.2f} to {RE['LD']:.2f}.", BODY),
      Paragraph(
    "The more useful part of the study is the review of the optimum. An unconstrained run reached a slightly lower fuel burn, "
    "but only by exploiting the parameterization with a zigzag twist and a local thickness bump that no engineer would accept. "
    "The same problem also converged to different local optima from different starting points, the near field induced drag "
    "implies a span efficiency above one, and the stress constraint is met at the optimization mesh but not at a finer one. "
    "Each of these is the kind of issue an evaluator must catch before trusting an optimized design.", BODY)]

s += [Paragraph("1. Problem definition", H1), Paragraph(
    "<b>Model.</b> OpenAeroStruct 2.12 couples a vortex lattice method (31 spanwise by 3 chordwise nodes on the full span, "
    "symmetric half model) with a wingbox beam finite element model built from the 10% to 60% chord portion of the NASA "
    "SC(2)-0612 airfoil. Viscous drag uses a flat plate skin friction estimate with a form factor, and wave drag uses the "
    "Korn equation. Material is aluminum 7075 (E = 73.1 GPa, yield 420 MPa, density 2,780 kg/m³) with a safety factor of 1.5, "
    "so the allowable von Mises stress is 280 MPa. The geometry is the uCRM based wing that ships with OpenAeroStruct.", BODY),
      Paragraph(
    "<b>Flight points.</b> Cruise at Mach 0.85 and 0.348 kg/m³ with lift coefficient fixed at 0.5. Maneuver at Mach 0.64, sea "
    "level, load factor 2.5, with lift equal to weight. Fuel burn comes from the Breguet range equation with a thrust specific "
    "fuel consumption of 0.53 1/h. Engine masses (10 t each) relieve the wing at 37% of the semi-span.", BODY),
      Paragraph(
    "<b>Optimization.</b> Objective: fuel burn. Design variables: four twist control points, four t/c control points "
    "(0.07 to 0.20), four spar and four skin thickness control points (3 mm to 100 mm), both angles of attack and the fuel "
    "mass. Constraints: CL = 0.5 in cruise, L = W at 2.5 g, aggregated (KS) stress failure at 2.5 g, fuel volume, and fuel "
    "mass consistency. Optimizer: SLSQP in OpenMDAO with analytic coupled adjoint gradients, tolerance 1e-6. The "
    "<b>realistic</b> variant adds two monotonicity constraints: t/c and twist may not decrease from tip to root.", BODY)]

rows = [["", "Baseline", "Free optimum", "Realistic optimum"],
        ["Fuel burn [t]", f"{B['fuelburn']/1e3:.2f}", f"{FR['fuelburn']/1e3:.2f}  ({pct(FR['fuelburn'], B['fuelburn'])})",
         f"{RE['fuelburn']/1e3:.2f}  ({pct(RE['fuelburn'], B['fuelburn'])})"],
        ["Cruise L/D", f"{B['LD']:.2f}", f"{FR['LD']:.2f}", f"{RE['LD']:.2f}"],
        ["Wingbox mass [t]", f"{B['wingbox']/1e3:.2f}", f"{FR['wingbox']/1e3:.2f}", f"{RE['wingbox']/1e3:.2f}"],
        ["Peak von Mises at 2.5 g [MPa]", f"{B['vm_max_MPa']:.0f}  (fails)", f"{FR['vm_max_MPa']:.0f}", f"{RE['vm_max_MPa']:.0f}"],
        ["Fuel volume margin [m³]", f"{B['fuel_vol_margin']:.1f}  (fails)", f"{FR['fuel_vol_margin']:.1f}", f"{RE['fuel_vol_margin']:.1f}"],
        ["CDi / CDv / CDw  [counts]", f"{B['CDi']*1e4:.0f} / {B['CDv']*1e4:.0f} / {B['CDw']*1e4:.1f}",
         f"{FR['CDi']*1e4:.0f} / {FR['CDv']*1e4:.0f} / {FR['CDw']*1e4:.1f}", f"{RE['CDi']*1e4:.0f} / {RE['CDv']*1e4:.0f} / {RE['CDw']*1e4:.1f}"],
        ["Span efficiency, Trefftz fit", f"{B['e_trefftz']:.3f}", f"{FR['e_trefftz']:.3f}", f"{RE['e_trefftz']:.3f}"]]
s += [Paragraph("2. Results", H1), table(rows, [W * 0.31, W * 0.21, W * 0.24, W * 0.24]),
      Paragraph("Table 1. Baseline is the initial uCRM design trimmed to the same flight conditions. Drag in counts (1e-4). "
                "Total CD also includes a fixed 78 count allowance for the fuselage and tail.", CAP),
      fig("figures/06_summary.png"),
      Paragraph("Figure 2. Fuel burn, cruise L/D and wingbox mass. The optimizer adds structure where the baseline was overstressed "
                "and recovers the weight penalty through lower induced drag. Note the truncated vertical axes.", CAP),
      fig("figures/02_span_loading.png", W * 0.82),
      Paragraph("Figure 3. Cruise span loading. The baseline is strongly root loaded (e = 0.83). Both optima move load outboard "
                "toward the elliptic distribution, stopping short of it because outboard load raises the root bending moment and "
                "therefore wingbox weight. This is the expected aerostructural compromise.", CAP),
      fig("figures/07_front_view_deflection.png", W * 0.85),
      fig("figures/08_baseline_vs_optimum_3d.png"),
      Paragraph("Figure 4b. Baseline and realistic optimum at 2.5 g on the same color scale; magenta marks stress above the allowable.", CAP),
      Paragraph("Figure 4. Leading edge vertical position of the realistic optimum, equal axis scale. Tip deflection is 1.8 m in cruise and 4.3 m at 2.5 g, 15% of the semi-span.", CAP),
      fig("figures/04_stress_utilization.png", W * 0.82),
      Paragraph("Figure 5. Wingbox stress utilization at 2.5 g. The baseline exceeds the allowable by up to 20% between 25% and 50% "
                "semi-span. Both optima are fully stressed over most of the inner wing, as expected when weight is minimized.", CAP)]

s += [Paragraph("3. Engineering review of the optimum", H1),
      Paragraph(
    f"<b>3.1 The free optimum exploits the parameterization.</b> With four control points and a single cruise condition, the free "
    f"optimizer produced a zigzag twist ({', '.join(f'{v:.1f}' for v in FR['twist'][::-1])} deg from root to tip) and a local "
    f"thickness bump to t/c = {max(FR['tc']):.2f} at two thirds of the semi-span, between 0.08 and 0.07 sections (Figure 6). "
    f"The bump enlarges the wingbox and the fuel volume where it is cheap in wave drag at this single Mach number, and the twist "
    f"oscillation trims the span loading around it. Neither shape would survive off design conditions, loft smoothness "
    f"requirements or manufacturing. Adding monotonic t/c and twist constraints removes both features at a cost of only "
    f"{100*(RE['fuelburn']/FR['fuelburn']-1):.1f}% in fuel burn, which is the price of realism in this model. The realistic optimum "
    f"settles on a constant twist, meaning the optimizer would prefer wash in; with only one cruise point there is nothing to "
    f"penalize it, so a second flight condition or a buffet margin would be the next constraint to add.", BODY),
      fig("figures/03_design_variables.png"),
      Paragraph("Figure 6. Twist and t/c control points. Root at 0, tip at 1.", CAP),
      Paragraph(
    f"<b>3.2 The problem has multiple local optima.</b> The same free problem started from the baseline converged to "
    f"{free_b['AS_point_0.fuelburn']/1e3:.2f} t, with a twist peak of {max(free_b['wing.twist_cp']):.1f} deg, while the restart "
    f"from the realistic solution reached {FR['fuelburn']/1e3:.2f} t. A 2% spread between two converged SLSQP runs means a "
    f"single run cannot be reported as the optimum; multistart is required.", BODY),
      Paragraph(
    f"<b>3.3 Induced drag accounting.</b> The near field induced drag implies span efficiencies of {RE['e_nearfield']:.2f} "
    f"(realistic) and {FR['e_nearfield']:.2f} (free), computed as e = CL²/(π AR CDi). For a planar wing Munk's theorem limits e to "
    f"1.0, and the bending deflection here is not large enough to justify the excess. An independent far field estimate, a "
    f"four term Fourier fit of the computed span loading, gives {RE['e_trefftz']:.3f} and {FR['e_trefftz']:.3f}, which are "
    f"physically plausible. This indicates the near field integration with three chordwise nodes underestimates induced drag "
    f"by roughly {100*(RE['e_nearfield']/RE['e_trefftz']-1):.0f}%, so absolute fuel burn is optimistic, although the ranking "
    f"between designs is unchanged.", BODY),
      Paragraph(
    f"<b>3.4 Mesh dependence.</b> Holding the realistic design fixed and retrimming at 15 to 61 spanwise nodes (Figure 7), "
    f"fuel burn converges at order {M['order_p']:.2f} toward {M['F_extrapolated']/1e3:.2f} t by Richardson extrapolation; the "
    f"31 node result is {abs(M['err_ny31_pct']):.1f}% low. More important, the peak stress at 61 nodes is "
    f"{M['vm_max_MPa']['61']:.0f} MPa, {100*(M['vm_max_MPa']['61']/280-1):.1f}% above the allowable. A design that is "
    f"exactly at its stress limit on the optimization mesh is not guaranteed feasible on a finer one. The fix is to optimize at "
    f"41 nodes or more, or to carry a 2% stress margin.", BODY),
      fig("figures/05_mesh_study.png"),
      Paragraph("Figure 7. Mesh study with the realistic design fixed and both flight points retrimmed.", CAP),
      Paragraph(
    f"<b>3.5 Bookkeeping check.</b> Fuel burn was recomputed by hand from the Breguet equation, W_fuel = W_end (exp(R c / (V L/D)) "
    f"- 1), with W_end = 128 t + 15 t reserve + 20 t engines + wing structural mass. The hand value matches the model output "
    f"to rounding for all three designs ({RE['breguet']/1e3:.2f} t for the realistic optimum), confirming the mission and "
    f"weight accounting.", BODY)]

s += [Paragraph("4. Checklist for judging an optimized wing", H1), Paragraph(
    "The findings above generalize into a review checklist that applies to any optimized wing, whether produced by a person or "
    "by an AI model: (1) every constraint active or satisfied with a stated margin, including at a finer mesh; (2) design "
    "variables smooth and monotonic where physics and manufacturing require it, with no oscillation between control points; "
    "(3) span efficiency at or below one for a planar wing, checked in the far field; (4) span loading between the elliptic and "
    "a root loaded distribution, consistent with the structural weight trade; (5) wingbox fully stressed where weight was "
    "minimized and lightly stressed near the tip; (6) the same optimum, within tolerance, from more than one starting point; "
    "(7) fuel burn reproducible by hand from L/D and weights.", BODY)]

s += [Paragraph("5. Limitations and reproducibility", H1), Paragraph(
    "Low fidelity model: VLM with empirical viscous and wave drag, beam wingbox, no buckling or aeroelastic flutter "
    "constraint, single cruise point. The fuselage and airfoil in the 3D renders are illustrative only. All inputs are public "
    "(OpenAeroStruct uCRM based example). Run study.py, then post.py, render.py and report.py; total run time is under ten "
    "minutes on a laptop. Results, scripts and figures are in the repository.", BODY)]


def deco(cv, doc):
    cv.saveState(); cv.setFont("C", 8.5); cv.setFillColor(colors.grey)
    cv.drawString(18 * mm, 10 * mm, "uCRM aerostructural optimization  |  Enzo Alves Zanatta")
    cv.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}"); cv.restoreState()


SimpleDocTemplate("uCRM_Aerostructural_Optimization_Report.pdf", pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                  topMargin=15 * mm, bottomMargin=16 * mm, title="Aerostructural Optimization of the uCRM Wing",
                  author="Enzo Alves Zanatta").build(s, onFirstPage=deco, onLaterPages=deco)
print("report ok")
