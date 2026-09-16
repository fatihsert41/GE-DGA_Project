"""Generates the architecture diagrams: SVG -> (headless Edge) -> PNG.

Run (from the project root):
    python docs/architecture/generate_diagrams.py

Outputs are written to docs/architecture/:
    01-system-architecture.png  three services, data stores, communication
    02-python-layers.png        layers and files of the FastAPI service
    03-uml-maintenance-domain.png  UML class diagram of the .NET service

The diagrams are drawn by code, not by hand: when a file is renamed,
update the list and re-run the script. No third-party packages needed;
PNG conversion uses Microsoft Edge, which ships with Windows.
"""
from __future__ import annotations

import html
import subprocess
import tempfile
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]

# --- Visual language (matches the ERP UI) ---------------------------------
BG = "#f4f6f9"
INK = "#1c2733"
MUTED = "#5b6878"
LINE = "#8a97a8"
SURFACE = "#ffffff"
NAVY = "#1f3a5f"
FRONT = "#0d8a7a"     # frontend
PY = "#1b6ca8"        # Python
NET = "#8b4a9c"       # .NET
DATA = "#7a736a"      # data
FONT = "Segoe UI, Arial, sans-serif"
MONO = "Consolas, 'Courier New', monospace"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def text(x, y, s, size=14, color=INK, weight=400, anchor="start",
         font=FONT, italic=False):
    style = ' font-style="italic"' if italic else ""
    return (f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
            f'fill="{color}" font-weight="{weight}" text-anchor="{anchor}"'
            f'{style}>{esc(s)}</text>')


def rect(x, y, w, h, fill=SURFACE, stroke=LINE, rx=8, sw=1.2, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')


def panel(x, y, w, h, title, subtitle, color):
    """Service box with a coloured title band."""
    return "".join([
        rect(x, y, w, h, SURFACE, color, 10, 2),
        f'<path d="M{x} {y + 10} a10 10 0 0 1 10 -10 h{w - 20} '
        f'a10 10 0 0 1 10 10 v44 h{-w} z" fill="{color}"/>',
        text(x + 18, y + 26, title, 17, "#fff", 600),
        text(x + 18, y + 45, subtitle, 12.5, "#e8eef5"),
    ])


def chip_width(label, size=12.5):
    return int(len(label) * size * 0.56) + 18


def chips(x, y, max_w, items, color, size=12.5, gap=8):
    """Lays out file names as wrapping chips; returns the final y."""
    out, cx, cy = [], x, y
    h = size + 12
    for label in items:
        w = chip_width(label, size)
        if cx + w > x + max_w:
            cx, cy = x, cy + h + gap
        out.append(rect(cx, cy, w, h, "#fff", color, 5, 1))
        out.append(text(cx + 9, cy + h - 8, label, size, INK, 400,
                        font=MONO))
        cx += w + gap
    return "".join(out), cy + h


def cylinder(x, y, w, h, title, sub, color=DATA):
    ry = 10
    return "".join([
        f'<path d="M{x} {y + ry} v{h - 2 * ry} a{w / 2} {ry} 0 0 0 {w} 0 '
        f'v{-(h - 2 * ry)}" fill="#fff" stroke="{color}" stroke-width="1.8"/>',
        f'<ellipse cx="{x + w / 2}" cy="{y + ry}" rx="{w / 2}" ry="{ry}" '
        f'fill="#efece6" stroke="{color}" stroke-width="1.8"/>',
        text(x + w / 2, y + h / 2 + 8, title, 14, INK, 600, "middle", MONO),
        text(x + w / 2, y + h / 2 + 27, sub, 11.5, MUTED, 400, "middle"),
    ])


def arrow(points, label=None, lx=None, ly=None, dashed=False, color=INK,
          anchor="start", both=False):
    pts = " ".join(f"{px},{py}" for px, py in points)
    d = ' stroke-dasharray="6 5"' if dashed else ""
    start = ' marker-start="url(#arrow-start)"' if both else ""
    out = (f'<polyline points="{pts}" fill="none" stroke="{color}" '
           f'stroke-width="1.8"{d} marker-end="url(#arrow)"{start}/>')
    if label:
        for i, line in enumerate(label.split("\n")):
            out += text(lx, ly + i * 16, line, 12.5, INK,
                        600 if i == 0 else 400, anchor)
    return out


def svg(w, h, body, title, subtitle):
    defs = f"""<defs>
<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8"
 markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>
<marker id="arrow-start" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8"
 markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>
<marker id="hollow" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="10"
 markerHeight="10" orient="auto"><path d="M0,0 L11,6 L0,12" fill="none" stroke="{INK}" stroke-width="1.4"/></marker>
</defs>"""
    head = (rect(0, 0, w, 76, NAVY, NAVY, 0, 0)
            + text(40, 36, title, 24, "#fff", 600)
            + text(40, 60, subtitle, 13.5, "#c9d6e6"))
    foot = text(w - 40, h - 16, "TransformerAI · DGA-based transformer fault "
                "prediction and maintenance planning", 11.5, MUTED, 400, "end")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" '
            f'height="{h}" viewBox="0 0 {w} {h}">{defs}'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>{head}{body}{foot}'
            f'</svg>')


# ======================================================================
# 1) System architecture
# ======================================================================
def system_architecture():
    W, H = 1600, 1010
    b = []

    # User
    b.append(rect(40, 150, 250, 330, SURFACE, NAVY, 10, 2))
    b.append(text(60, 182, "User", 18, INK, 600))
    b.append(text(60, 204, "Browser · employee no. + password", 12.5, MUTED))
    depts = ["Management", "Maintenance Planning", "Oil Laboratory",
             "Electrical Testing", "Field Service", "Engineering",
             "System Administration"]
    b.append(text(60, 236, "Departments", 12.5, INK, 600))
    for i, d in enumerate(depts):
        b.append(rect(60, 248 + i * 30, 210, 24, "#f7f8fa", LINE, 4, 1))
        b.append(text(70, 265 + i * 30, d, 12.5))

    # Frontend
    fx, fy, fw, fh = 340, 110, 410, 470
    b.append(panel(fx, fy, fw, fh, "Frontend · React + Vite",
                   ":5173 development · nginx :8080 (Docker)", FRONT))
    s, end = chips(fx + 18, fy + 74, fw - 36, [
        "App.jsx", "api.js", "LoginScreen.jsx", "FleetOverview.jsx",
        "TransformerDetail.jsx", "HealthPanel.jsx", "OilQualityPanel.jsx",
        "ElectricalPanel.jsx", "MaintenancePanel.jsx", "ReviewQueue.jsx",
        "ModelReviewQueue.jsx", "LimitsQueue.jsx", "RcaQueue.jsx",
        "AdminPanel.jsx", "NotificationsPanel.jsx", "+17 screens"], FRONT)
    b.append(s)
    b.append(text(fx + 18, end + 30, "ERP shell — transaction codes", 13, INK, 600))
    b.append(text(fx + 18, end + 50, "FL01 · TS01 · NA01 · BK01 · MH01–04",
                  12.5, MUTED, font=MONO))
    b.append(text(fx + 18, end + 68, "YN01 · PR01 · BL01 · AD01 · PW01",
                  12.5, MUTED, font=MONO))
    b.append(rect(fx + 18, fy + fh - 78, fw - 36, 60, "#eef7f5", FRONT, 6, 1))
    b.append(text(fx + 32, fy + fh - 55, "Reverse proxy", 13, INK, 600))
    b.append(text(fx + 32, fy + fh - 33, "/api  → :8000     /maint → :5080",
                  13, INK, font=MONO))

    # Python service
    px, py_, pw, ph = 820, 100, 460, 420
    b.append(panel(px, py_, pw, ph, "Diagnostics Service · Python FastAPI",
                   ":8000 · ML and domain rules", PY))
    layers = [
        ("routers/", "17 modules · HTTP endpoints"),
        ("services/", "orchestration: data + rules"),
        ("core/", "pure rules: IEC 60599, Duval, IEEE C57.104"),
        ("ml/", "RandomForest · SHAP · synthetic data generator"),
        ("auth.py", "token validation, permission checks"),
        ("database.py", "SQLite access, idempotent migrations"),
    ]
    for i, (name, desc) in enumerate(layers):
        yy = py_ + 76 + i * 54
        b.append(rect(px + 18, yy, pw - 36, 44, "#eef4fa", PY, 6, 1))
        b.append(text(px + 32, yy + 28, name, 14, INK, 700, font=MONO))
        b.append(text(px + 150, yy + 28, desc, 12.5, MUTED))

    # .NET service
    nx, ny, nw, nh = 820, 610, 460, 320
    b.append(panel(nx, ny, nw, nh, "Maintenance Planning Service · ASP.NET Core",
                   ":5080 · C# · EF Core · xUnit", NET))
    net_layers = [
        ("Program.cs", "Minimal API endpoints"),
        ("Services/", "WorkOrderPlanner · AssignmentService · RcaRules"),
        ("", "AuthService · TokenIssuer · Notification*"),
        ("Data/", "MaintenanceDbContext · *Repository"),
        ("Models/", "WorkOrder · Technician · RCA · Session"),
    ]
    for i, (name, desc) in enumerate(net_layers):
        yy = ny + 74 + i * 46
        if name:
            b.append(rect(nx + 18, yy, nw - 36, 38 if name != "Services/" else 84,
                          "#f5eef7", NET, 6, 1))
            b.append(text(nx + 32, yy + 25, name, 14, INK, 700, font=MONO))
        b.append(text(nx + 150, yy + 25, desc, 12.5, MUTED))

    # Data stores
    b.append(cylinder(1370, 150, 190, 110, "dga.db", "SQLite · measurements, tests"))
    b.append(cylinder(1370, 330, 190, 110, "model.joblib", "trained model + threshold"))
    b.append(cylinder(1370, 700, 190, 120, "maintenance.db",
                      "SQLite · work orders, staff"))

    # Arrows
    b.append(arrow([(290, 315), (338, 315)], "HTTP", 296, 305))
    b.append(arrow([(750, 250), (818, 250)], "/api", 758, 240))
    b.append(text(758, 272, "JSON", 11.5, MUTED))
    b.append(arrow([(750, 560), (785, 560), (785, 760), (818, 760)],
                   "/maint", 777, 680, anchor="end"))
    b.append(text(777, 696, "REST · JSON", 11.5, MUTED, anchor="end"))
    b.append(arrow([(930, 608), (930, 522)],
                   "reads risk, never stores it\nMlServiceClient → /fleet/overview",
                   940, 555))
    b.append(arrow([(1210, 608), (1210, 522)], "HMAC token",
                   1222, 555, dashed=True))
    b.append(text(1222, 571, ".NET issues", 11.5, MUTED))
    b.append(text(1222, 587, "Python verifies", 11.5, MUTED))
    b.append(arrow([(1280, 205), (1368, 205)]))
    b.append(arrow([(1280, 385), (1368, 385)]))
    b.append(arrow([(1280, 760), (1368, 760)]))

    # Principles
    b.append(text(40, 600, "Architecture principles", 15, INK, 600))
    principles = [
        "No shared database — each service owns its data",
        ".NET consumes Python over HTTP only",
        "Business rules live in pure, I/O-free classes",
        "Permissions are bound to departments, not roles",
        "Work orders keep working while Python is down",
        "Docker Compose · GitHub Actions CI · 527 tests",
    ]
    for i, p in enumerate(principles):
        b.append(f'<circle cx="52" cy="{627 + i * 30}" r="4" fill="{NAVY}"/>')
        b.append(text(64, 632 + i * 30, p, 13))

    return svg(W, H, "".join(b), "System Architecture",
               "Polyglot microservices: React frontend · Python diagnostics · "
               ".NET maintenance planning"), W, H


# ======================================================================
# 2) Python service layers
# ======================================================================
def python_layers():
    W, H = 1600, 1060
    b = []
    X, Wd = 90, 1170

    def layer(y, h, title, sub, items, color, x=X, w=Wd, fill="#fff"):
        b.append(rect(x, y, w, h, fill, color, 10, 1.8))
        b.append(text(x + 20, y + 30, title, 17, color, 700, font=MONO))
        b.append(text(x + 20, y + 50, sub, 12.5, MUTED))
        s, _ = chips(x + 20, y + 66, w - 40, items, color)
        b.append(s)

    b.append('<text x="0" y="0" font-family="%s" font-size="12.5" '
             'fill="%s" transform="translate(48 480) rotate(-90)" '
             'text-anchor="middle">Request flow</text>' % (FONT, MUTED))
    b.append(arrow([(62, 110), (62, 860)]))

    layer(100, 140, "routers/", "HTTP layer — validation, permissions, status codes",
          ["predict.py", "explain.py", "compare.py", "trend.py",
           "fleet.py", "transformers.py", "oil.py", "electrical.py",
           "components.py", "physical.py", "health_index.py",
           "lifecycle.py", "reviews.py", "model_reviews.py", "limits.py",
           "schematic.py", "main.py"], PY, fill="#f3f8fc")
    layer(270, 140, "services/", "Orchestration — combines the database with the rules",
          ["diagnosis.py", "fleet.py", "health.py", "trend.py", "oil.py",
           "electrical.py", "components.py", "physical.py", "review.py",
           "model_review.py", "limits.py", "schematic.py"], PY)
    layer(440, 300, "core/", "Pure domain rules — no I/O, directly testable",
          ["gases.py", "duval.py", "rogers.py", "iec_ratio.py",
           "key_gas.py", "classify.py", "risk.py", "assets.py",
           "nameplate.py", "oil_quality.py", "electrical.py",
           "components.py", "physical.py", "health_index.py",
           "review.py", "expert_label.py", "asset_limits.py",
           "lifecycle.py", "rate.py"], "#2f5d3a", w=560, fill="#f4f8f3")
    layer(440, 300, "ml/", "Machine learning — training, inference, evaluation",
          ["synth.py", "synth_oil.py", "synth_electrical.py",
           "features.py", "hybrid.py", "train.py", "predictor.py",
           "calibration.py", "safety_eval.py", "diagnostics.py",
           "real_data.py", "evaluate_real.py", "experiments.py",
           "rate_eval.py", "seed.py"], "#7a4a12", x=X + 610, w=560,
          fill="#fbf6ef")
    layer(770, 110, "infrastructure", "Persistence, identity and schemas",
          ["database.py", "auth.py", "schemas.py"], INK, w=560)
    b.append(cylinder(X + 700, 770, 200, 110, "dga.db", "SQLite"))
    b.append(cylinder(X + 950, 770, 220, 110, "model.joblib", "artifacts/"))
    b.append(arrow([(X + 560, 825), (X + 698, 825)]))
    b.append(arrow([(X + 890, 740), (X + 1060, 768)]))
    b.append(text(X + 985, 748, "written by train.py", 11.5, MUTED))

    for yy in (242, 412):
        b.append(arrow([(X + 585, yy), (X + 585, yy + 26)]))
    b.append(arrow([(X + 280, 412), (X + 280, 438)]))
    b.append(arrow([(X + 890, 412), (X + 890, 438)]))

    # Right column: notes
    ax = 1300
    notes = [
        ("Layering rule", ["Dependencies only point down.",
                           "core/ imports no other layer."]),
        ("Why a pure core?", ["Rules are tested without a",
                                 "DB or HTTP: 300 pytest tests."]),
        ("Explainability", ["Every score ships with its parts:",
                              "weight × score, no black box."]),
        ("Data policy", ["No corporate data; synthetic",
                             "data from IEC 60599 signatures,",
                             "validated on a public dataset."]),
        ("Train/serve consistency", ["The threshold is measured on",
                                     "the served model and saved."]),
    ]
    yy = 108
    for title, lines in notes:
        hh = 34 + len(lines) * 18
        b.append(rect(ax, yy, 260, hh, SURFACE, LINE, 8, 1))
        b.append(text(ax + 14, yy + 22, title, 13.5, INK, 600))
        for i, ln in enumerate(lines):
            b.append(text(ax + 14, yy + 42 + i * 18, ln, 12.5, MUTED))
        yy += hh + 14

    # Example request flow
    b.append(text(X, 930, "Example flow — a new DGA measurement", 15, INK, 600))
    flow = ["POST /predict", "routers/predict.py", "services/diagnosis.py",
            "ml/predictor.py + core/classify.py + core/risk.py",
            "database.save_measurement", "dga.db"]
    cx = X
    for i, step in enumerate(flow):
        w = chip_width(step, 12.5)
        b.append(rect(cx, 948, w, 30, "#fff", PY, 5, 1.2))
        b.append(text(cx + 9, 968, step, 12.5, INK, font=MONO))
        if i < len(flow) - 1:
            b.append(arrow([(cx + w + 2, 963), (cx + w + 22, 963)]))
        cx += w + 26

    return svg(W, H, "".join(b), "Python Diagnostics Service — Layers",
               "backend/app/ · FastAPI · each chip is a source file"), W, H


# ======================================================================
# 3) UML class diagram — .NET maintenance domain
# ======================================================================
def uml_class(b, x, y, w, name, fields, methods=(), stereotype=None,
              color=NET):
    head = 50 if stereotype else 36
    h = head + len(fields) * 20 + 12 + (len(methods) * 20 + 12 if methods else 0)
    b.append(rect(x, y, w, h, SURFACE, color, 4, 1.6))
    b.append(f'<rect x="{x}" y="{y}" width="{w}" height="{head}" rx="4" '
             f'fill="{color}"/>')
    if stereotype:
        b.append(text(x + w / 2, y + 18, f"«{stereotype}»", 11.5, "#eee",
                      400, "middle", italic=True))
    b.append(text(x + w / 2, y + head - 12, name, 15, "#fff", 700, "middle"))
    yy = y + head + 20
    for f in fields:
        b.append(text(x + 12, yy, f, 12.5, INK, font=MONO))
        yy += 20
    if methods:
        yy -= 8
        b.append(f'<line x1="{x}" y1="{yy}" x2="{x + w}" y2="{yy}" '
                 f'stroke="{color}" stroke-width="1"/>')
        yy += 22
        for m in methods:
            b.append(text(x + 12, yy, m, 12.5, INK, font=MONO))
            yy += 20
    return h


def mult(x, y, s, anchor="start"):
    return text(x, y, s, 12.5, NAVY, 700, anchor, MONO)


def uml_domain():
    W, H = 1600, 1080
    b = []
    ENUM = "#56606e"

    uml_class(b, 60, 110, 330, "Technician", [
        "+ Id: string", "+ EmployeeNo: string", "+ Name: string",
        "+ Department: Department", "+ Specialty: Specialty",
        "+ MaxOpenOrders: int", "+ IsActive: bool",
        "+ PasswordHash: string", "+ MustChangePassword: bool",
        "+ FailedAttempts: int", "+ LockedUntil: DateTime?",
        "+ WorkOrders: List<WorkOrder>"])
    uml_class(b, 620, 110, 340, "WorkOrder", [
        "+ Id: string", "+ Seq: int  {unique}", "+ TransformerId: string",
        "+ Kind: WorkOrderKind", "+ Title: string", "+ Reason: string?",
        "+ Status: WorkOrderStatus", "+ Priority: double",
        "+ TechnicianId: string?", "+ CreatedAt: DateTime",
        "+ DueDate: DateOnly?", "+ CompletedAt: DateTime?",
        "+ CompletionNote: string?"])
    uml_class(b, 1180, 110, 370, "RootCauseAnalysis", [
        "+ Id: string  «RCA-{Seq}»", "+ WorkOrderId: string  {unique}",
        "+ TransformerId: string", "+ FailureMode: FailureMode",
        "+ Finding: string", "+ RootCause: string",
        "+ CorrectiveAction: string", "+ PreventiveAction: string?",
        "+ RecordedAt: DateTime", "+ RecordedById: string"])
    uml_class(b, 60, 560, 330, "Session", [
        "+ TokenHash: string", "+ TechnicianId: string",
        "+ CreatedAt: DateTime", "+ ExpiresAt: DateTime",
        "+ LastSeenAt: DateTime"])
    uml_class(b, 60, 800, 330, "UserAuditEvent", [
        "+ Id: long", "+ At: DateTime", "+ Action: string",
        "+ TargetId: string", "+ ActorId: string?", "+ Detail: string?"])
    b.append(text(225, 1020, "no FK · never deleted (audit trail)", 11.5,
                  MUTED, 400, "middle", italic=True))
    uml_class(b, 620, 560, 340, "Notification", [
        "+ Id: string", "+ WorkOrderId: string?", "+ RecipientId: string",
        "+ SenderId: string?", "+ Channel: NotificationChannel",
        "+ Status: NotificationStatus", "+ Subject: string",
        "+ Body: string", "+ Priority: double", "+ CreatedAt: DateTime",
        "+ ReadAt: DateTime?"])
    uml_class(b, 620, 880, 340, "WorkOrderTransitions", [], [
        "+ IsAllowed(from, to): bool",
        "+ Next(from): IReadOnlyList",
        "+ Explain(from, to): string"], stereotype="static")

    uml_class(b, 1180, 420, 180, "WorkOrderStatus",
              ["Planned", "InProgress", "Done", "Cancelled"],
              stereotype="enum", color=ENUM)
    uml_class(b, 1180, 590, 180, "WorkOrderKind",
              ["Inspection", "Sampling", "Repair", "Replacement", "Test"],
              stereotype="enum", color=ENUM)
    uml_class(b, 1180, 780, 180, "Department",
              ["Management", "OilLaboratory", "ElectricalTesting",
               "MaintenancePlanning", "FieldService", "Engineering",
               "SystemAdmin"], stereotype="enum", color=ENUM)
    uml_class(b, 1380, 420, 170, "FailureMode",
              ["Insulation", "Winding", "Core", "Bushing", "TapChanger",
               "Cooling", "Oil", "Protection", "External",
               "Undetermined"], stereotype="enum", color=ENUM)
    uml_class(b, 1380, 740, 170, "Pure services", [
        "WorkOrderPlanner", "AssignmentService", "RcaRules",
        "PasswordPolicy", "UserAdminRules"], stereotype="service",
        color="#2f5d3a")

    # Associations (EF Core foreign keys)
    b.append(f'<line x1="390" y1="240" x2="620" y2="240" stroke="{INK}" '
             f'stroke-width="1.6"/>')
    b.append(mult(398, 230, "0..1"))
    b.append(mult(612, 230, "0..*", "end"))
    b.append(text(505, 262, "assigned to", 12.5, INK, 600, "middle"))
    b.append(text(505, 279, "OnDelete: SetNull", 11.5, MUTED, 400, "middle"))

    b.append(f'<line x1="960" y1="240" x2="1180" y2="240" stroke="{INK}" '
             f'stroke-width="1.6"/>')
    b.append(mult(968, 230, "1"))
    b.append(mult(1172, 230, "0..1", "end"))
    b.append(text(1070, 262, "analysed by", 12.5, INK, 600, "middle"))
    b.append(text(1070, 279, "Done only · Restrict", 11.5, MUTED, 400,
                  "middle"))

    b.append(f'<line x1="225" y1="416" x2="225" y2="560" stroke="{INK}" '
             f'stroke-width="1.6"/>')
    b.append(mult(233, 434, "1"))
    b.append(mult(233, 552, "0..*"))
    b.append(text(275, 492, "signs in", 12.5, INK, 600))
    b.append(text(275, 509, "all revoked on password change", 11.5, MUTED))

    b.append(f'<line x1="790" y1="436" x2="790" y2="560" stroke="{INK}" '
             f'stroke-width="1.6"/>')
    b.append(mult(798, 454, "0..1"))
    b.append(mult(798, 552, "0..*"))
    b.append(text(850, 500, "raises", 12.5, INK, 600))
    b.append(text(850, 517, "OnDelete: Cascade", 11.5, MUTED))

    b.append(f'<polyline points="390,380 500,380 500,700 620,700" '
             f'fill="none" stroke="{INK}" stroke-width="1.6"/>')
    b.append(mult(398, 372, "1"))
    b.append(mult(612, 692, "0..*", "end"))
    b.append(text(510, 650, "recipient", 12.5, INK, 600))

    # Dependencies (dashed)
    b.append(f'<line x1="960" y1="370" x2="1178" y2="470" stroke="{INK}" '
             f'stroke-width="1.3" stroke-dasharray="6 5" '
             f'marker-end="url(#hollow)"/>')
    b.append(f'<line x1="960" y1="300" x2="1178" y2="640" stroke="{INK}" '
             f'stroke-width="1.3" stroke-dasharray="6 5" '
             f'marker-end="url(#hollow)"/>')
    b.append(f'<line x1="1465" y1="376" x2="1465" y2="418" stroke="{INK}" '
             f'stroke-width="1.3" stroke-dasharray="6 5" '
             f'marker-end="url(#hollow)"/>')
    b.append(f'<line x1="960" y1="940" x2="1178" y2="500" stroke="{INK}" '
             f'stroke-width="1.3" stroke-dasharray="6 5" '
             f'marker-end="url(#hollow)"/>')

    # State machine note
    b.append(rect(990, 990, 560, 50, "#fffbe8", "#b9a24a", 4, 1))
    b.append(text(1004, 1011, "State machine:  Planned → InProgress → Done",
                  12.5, INK, 600, font=MONO))
    b.append(text(1004, 1029, "Planned/InProgress → Cancelled → Planned · "
                  "Done is terminal", 12, MUTED, font=MONO))

    # Legend
    b.append(f'<line x1="60" y1="1050" x2="100" y2="1050" stroke="{INK}" '
             f'stroke-width="1.6"/>')
    b.append(text(108, 1054, "association (EF Core foreign key)", 12, MUTED))
    b.append(f'<line x1="330" y1="1050" x2="370" y2="1050" stroke="{INK}" '
             f'stroke-width="1.3" stroke-dasharray="6 5" '
             f'marker-end="url(#hollow)"/>')
    b.append(text(380, 1054, "uses / dependency", 12, MUTED))

    return svg(W, H, "".join(b), "Maintenance Planning Domain — UML Class Diagram",
               "maintenance/TransformerAI.Maintenance.Api/Models · "
               "ASP.NET Core + EF Core (SQLite)"), W, H


def render(name, content, w, h, edge):
    src = OUT / "src"
    src.mkdir(exist_ok=True)
    svg_path = src / f"{name}.svg"
    svg_path.write_text(content, encoding="utf-8")
    page = src / f"{name}.html"
    page.write_text(
        '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;'
        f'overflow:hidden}}</style>{content}', encoding="utf-8")
    png = OUT / f"{name}.png"
    # Headless Edge occasionally exits before writing the file, so retry.
    for _ in range(4):
        subprocess.run([
            str(edge), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--force-device-scale-factor=2", f"--window-size={w},{h}",
            # Fresh profile: otherwise a headless instance may attach to an
            # already-open Edge window and exit without writing anything.
            f"--user-data-dir={tempfile.mkdtemp(prefix='edge-diagram-')}",
            "--no-first-run",
            f"--screenshot={png}", page.as_uri(),
        ], capture_output=True, timeout=90)
        if png.exists():
            break
        time.sleep(2)
    else:
        raise SystemExit(f"PNG was not produced: {png}")
    print(f"written: {png.relative_to(OUT.parent.parent)}")


def main():
    edge = next((p for p in EDGE_CANDIDATES if p.exists()), None)
    if edge is None:
        raise SystemExit("Microsoft Edge not found; SVGs are in src/.")
    for name, fn in [("01-system-architecture", system_architecture),
                     ("02-python-layers", python_layers),
                     ("03-uml-maintenance-domain", uml_domain)]:
        content, w, h = fn()
        render(name, content, w, h, edge)


if __name__ == "__main__":
    main()
