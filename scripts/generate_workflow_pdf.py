"""Generate a PDF: how this project was built vs professional practice."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether,
)

OUT = r"C:\Users\sikha\Videos\power\powerplant-dashboard\docs\Professional_Workflow_vs_This_Project.pdf"

ACCENT = colors.HexColor("#1a5276")
LIGHT = colors.HexColor("#eaf2f8")
GREY = colors.HexColor("#5d6d7e")
ROW_A = colors.white
ROW_B = colors.HexColor("#f4f6f7")

styles = getSampleStyleSheet()

def ps(name, **kw):
    base = dict(fontName="Helvetica", fontSize=10, leading=14, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, **base)

h1 = ps("H1", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=ACCENT, spaceAfter=6)
h2 = ps("H2", fontName="Helvetica-Bold", fontSize=13.5, leading=17, textColor=ACCENT, spaceBefore=14, spaceAfter=5)
h3 = ps("H3", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#21618c"), spaceBefore=8, spaceAfter=3)
body = ps("Body", spaceAfter=5)
bullet = ps("Bullet", leftIndent=12, bulletIndent=4, spaceAfter=3)
small = ps("Small", fontSize=9, leading=12, textColor=GREY)
cell = ps("Cell", fontSize=8.6, leading=11.4)
cellh = ps("CellH", fontName="Helvetica-Bold", fontSize=8.8, leading=11.5, textColor=colors.white)

story = []

# ---------- Cover ----------
story.append(Spacer(1, 60 * mm))
story.append(Paragraph("Building Monitoring Dashboards:", h1))
story.append(Paragraph("How Professionals Do It vs How We Did It", ps("CoverSub", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=GREY, spaceAfter=18)))
story.append(Paragraph(
    "A comparative workflow analysis of the <b>Powerplant Dashboard</b> project "
    "(Python / Plotly Dash / PostgreSQL / Docker Compose) against industry practice "
    "for production data applications — with a concrete improvement checklist for "
    "the next project.", body))
story.append(Spacer(1, 10 * mm))
story.append(Paragraph("Prepared for personal process improvement - August 2026", small))
story.append(PageBreak())

# ---------- 1. Executive summary ----------
story.append(Paragraph("1. Executive Summary", h1))
story.append(Paragraph(
    "This project got the <i>architecture</i> of a professional system roughly right: "
    "documentation-first planning (PROJECT_CONTEXT, REQUIREMENTS, ARCHITECTURE, DATABASE, "
    "UI_SPEC, IMPLEMENTATION_PLAN), a clean layered design (UI → services → repositories), "
    "an explicit test matrix, and a phase-by-phase execution plan with a Definition of Done.", body))
story.append(Paragraph(
    "Where it diverges from professional practice is mostly in the <i>process around the code</i>: "
    "no version-control workflow (branches/PRs/reviews), no CI pipeline, no schema migration tooling, "
    "no environment separation beyond local, no observability, and single-person execution without "
    "design review or iteration checkpoints. These gaps are normal for a solo development build — but they are exactly "
    "what to adopt next, because they are what makes teams ship reliably at scale.", body))
story.append(Paragraph(
    "<b>One-line takeaway:</b> professionals do not write dramatically better code than you; "
    "they surround similar code with review loops, automation, and operational safety nets.", ps(
        "Takeaway", fontName="Helvetica-Oblique", fontSize=10.5, leading=14, textColor=ACCENT)))

# ---------- 2. What we did ----------
story.append(Paragraph("2. How This Project Was Built (Observed Workflow)", h1))

rows_we = [
    ("Phase", "What actually happened"),
    ("Planning",
     "Written context documents first (mission, requirements, architecture, DB design, UI spec). "
     "Scope fixed explicitly: 30 plants / 71 transformers / 120 devices / 8 metrics."),
    ("Design",
     "Layered architecture decided up front: Dash UI must not run SQL; repositories own data access; "
     "services own domain calculations; strict identifier validation; demo auth isolated for later replacement."),
    ("Execution",
     "AI-assisted, phase-by-phase per IMPLEMENTATION_PLAN.md; small explicit modules; thin callbacks; "
     "run tests after each phase; no broad rewrites when small changes suffice."),
    ("Data",
     "Synthetic seed: ~1.38M readings over 30 days at 30-minute intervals; deterministic generation; "
     "energy cumulative, others statistical; integrity checks in tests (row counts, coverage, monotonicity)."),
    ("Verification",
     "pytest suite split into pure-logic (-m 'not db') and full DB-backed runs; Definition of Done phrased as "
     "a user journey (start Postgres, seed, log in, navigate, switch metrics, see correct KPIs...)."),
    ("Delivery",
     "Local only: docker-compose PostgreSQL + locally-run Dash app. No CI, no deployed environment, no monitoring."),
]
t = Table([[Paragraph(c, cellh if i == 0 else cell) for c in row] for i, row in enumerate(rows_we)],
          colWidths=[28*mm, 152*mm])
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [ROW_A, ROW_B]),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dbdb")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]))
story.append(t)

story.append(Paragraph(
    "<b>Strengths worth keeping:</b> docs-before-code, explicit scope boundaries ('do not expand unless instructed'), "
    "separation of concerns enforced by rule, honest synthetic-data labelling, and a user-journey Definition of Done.",
    body))

# ---------- 3. Professional lifecycle ----------
story.append(PageBreak())
story.append(Paragraph("3. How Professional Teams Build This Kind of System", h1))
story.append(Paragraph(
    "A production telemetry/monitoring dashboard typically moves through seven stages. "
    "Each stage has artefacts and rituals that exist to catch mistakes early, when they are cheap.", body))

stages = [
    ("3.1 Discovery & Requirements",
     ["Stakeholder interviews; written problem statement and success metrics (SLOs: e.g. 'dashboard p95 load < 2s').",
      "User personas and journeys (operator, engineer, manager) drive UI priorities.",
      "Requirements prioritised (MoSCoW); non-functional requirements named explicitly: freshness, retention, concurrency."]),
    ("3.2 Architecture & Design Review",
     ["Architecture Decision Records (ADRs): one short doc per decision (why Dash not Streamlit, why schema-per-app, why 30-min grain).",
      "Design review with peers before building; alternatives documented, not just chosen path.",
      "Capacity math done early: rows/day, query patterns, index strategy, partitioning plan for the readings table."]),
    ("3.3 Version Control & Collaboration",
     ["Trunk-based or short-lived feature branches; every change via Pull Request.",
      "Mandatory code review; small PRs (<400 lines); PR templates with checklists.",
      "Conventional commits; protected main branch; tags/releases."]),
    ("3.4 Continuous Integration / Delivery",
     ["CI on every push: lint (ruff), type-check (mypy), unit tests, then integration tests against a disposable Postgres service container.",
      "CD to a staging environment automatically; production deploy gated and reversible.",
      "Infrastructure as code from day one (compose file committed, env templated with .env.example, secrets in a manager)."]),
    ("3.5 Data Engineering Discipline",
     ["Schema migrations via Alembic — never hand-edited DDL; every change reversible and reviewed.",
      "Idempotent, versioned seeds/fixtures; data-quality checks (freshness, null rate, monotonicity) as automated tests or dbt-style checks.",
      "Explicit retention/partitioning policy for time-series data (readings will grow forever otherwise)."]),
    ("3.6 Testing Strategy (the pyramid)",
     ["Fast unit tests for pure logic (parsing, KPI math) — thousands, milliseconds each.",
      "Integration tests for repository + real Postgres in CI containers.",
      "Few end-to-end tests driving the real UI (Playwright) covering critical journeys only.",
      "Non-deterministic data handled with fixtures and property-based tests (hypothesis) where valuable."]),
    ("3.7 Observability & Operations",
     ["Structured logging with request/correlation IDs; errors surfaced to users as friendly messages, to logs as stack traces.",
      "Metrics (request latency, query time, refresh failures) exported to Prometheus/Grafana; alerting on staleness of ingest.",
      "Runbooks: 'what to do when readings stop arriving'; on-call expectations defined before launch, not after."]),
]
for title, items in stages:
    block = [Paragraph(title, h2)]
    for it in items:
        block.append(Paragraph(it, bullet, bulletText="-"))
    story.append(KeepTogether(block))

# ---------- 4. Gap analysis ----------
story.append(PageBreak())
story.append(Paragraph("4. Gap Analysis: Us vs Them", h1))

gap_rows = [
    ("Area", "This project", "Professional practice", "Impact if ignored"),
    ("Requirements",
     "Docs written up front by one person/AI pair; scope fixed.",
     "Stakeholder interviews, prioritised backlog, SLOs, iterative refinement with users.",
     "Building the right thing is luck; rework discovered late."),
    ("Decisions",
     "Rationale lives in CLAUDE.md prose.",
     "ADR per significant decision: context, options, consequence.",
     "In 6 months nobody remembers why Dash was chosen or what was rejected."),
    ("Version control",
     "Single branch, direct commits, AI-generated changes unreviewed.",
     "Feature branches, mandatory human review, protected main.",
     "No safety net; hard to bisect regressions; risky rollbacks."),
    ("CI/CD",
     "Tests run manually after phases.",
     "Every push: lint + types + tests + integration against ephemeral DB; auto-deploy staging.",
     "Breakage found late; 'works on my machine' drift."),
    ("Schema evolution",
     "Initial DDL created once; seed regenerated.",
     "Alembic migrations, forward + backward, applied identically in all environments.",
     "Any real client data forces painful manual migration work."),
    ("Environments",
     "Local dev only.",
     "dev / staging / prod parity via IaC; config by environment variables everywhere (already partly done).",
     "First deployment becomes a rewrite instead of a config change."),
    ("Testing",
     "Good pytest matrix for logic + DB; no UI-level E2E.",
     "Pyramid incl. Playwright journeys; flake budgets; coverage gates on changed code.",
     "Silent UI/callback regressions reach users undetected."),
    ("Data quality",
     "Seed integrity tested once at seed time.",
     "Continuous checks: freshness alerts, row-count monitors, anomaly detection on ingest.",
     "Dashboard confidently shows wrong/stale data - worst failure mode."),
    ("Observability",
     "None beyond pytest.",
     "Structured logs, latency/error metrics, alerting, dashboards about the dashboard.",
     "Failures invisible until a user complains."),
    ("Security",
     "Demo auth isolated; env config; secrets uncommitted.",
     "Threat model, dependency scanning, least-privilege DB roles, secret rotation, pen-test before launch.",
     "Demo auth pattern leaking into production; audit findings."),
    ("Delivery cadence",
     "Phase-by-phase toward one big Done.",
     "Two-week increments, each demoable and deployable; retrospective each cycle.",
     "Feedback arrives months late when course-correction is expensive."),
    ("Documentation",
     "Strong spec docs; README commands.",
     "Spec + ADRs + runbooks + CHANGELOG + onboarding guide kept alive with code.",
     "Knowledge locked in one head/session; handover impossible."),
]
tg = Table([[Paragraph(c, cellh if i == 0 else cell) for c in row] for i, row in enumerate(gap_rows)],
           colWidths=[26*mm, 48*mm, 62*mm, 44*mm])
style_cmds = [
    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dbdb")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]
for i in range(1, len(gap_rows)):
    style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_B if i % 2 == 0 else ROW_A))
tg.setStyle(TableStyle(style_cmds))
story.append(tg)

# ---------- 5. Workflow comparison ----------
story.append(PageBreak())
story.append(Paragraph("5. Same Task, Two Workflows: 'Add a New Metric'", h1))
story.append(Paragraph(
    "Concrete illustration using a task this project will genuinely face — adding a ninth metric "
    "(e.g. oil temperature) end to end:", body))

wf = [
    ("Step", "Our typical flow", "Professional team flow"),
    ("Plan",
     "Decide directly in session; edit METRIC config.",
     "Ticket created; acceptance criteria written; SLO impact checked; estimate given; sprint-planned."),
    ("DB",
     "Column added to seed generator + DDL re-created.",
     "Alembic migration written + reviewed; backfill script for existing rows; migration tested on staging snapshot."),
    ("Code",
     "Repository/service/component edits in one pass.",
     "Branch; metric added via existing config-driven extension point; unit tests first where practical."),
    ("Review",
     "Self-review / AI review in conversation.",
     "PR with diff, screenshots, migration note; reviewer checks query plan on large table; approve -> merge."),
    ("Verify",
     "pytest suite run manually.",
     "CI: lint, types, units, integration on ephemeral Postgres seeded with fixtures; E2E click-through on preview deploy."),
    ("Release",
     "Restart local app.",
     "Merge to main -> auto-deploy staging -> smoke test -> tagged release -> prod deploy with rollback plan."),
    ("After",
     "Move on.",
     "Monitor metric ingest freshness + chart latency; retrospective note; docs/CHANGELOG updated."),
]
tw = Table([[Paragraph(c, cellh if i == 0 else cell) for c in row] for i, row in enumerate(wf)],
           colWidths=[16*mm, 72*mm, 92*mm])
cmds = [
    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dbdb")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
]
for i in range(1, len(wf)):
    cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_B if i % 2 == 0 else ROW_A))
tw.setStyle(TableStyle(cmds))
story.append(tw)
story.append(Paragraph(
    "The professional flow is slower per change (~hours vs minutes) but scales to many contributors, "
    "many metrics, and a system that must not silently show wrong data.", body))

# ---------- 6. Improvement checklist ----------
story.append(PageBreak())
story.append(Paragraph("6. Your Checklist for the Next Project", h1))
story.append(Paragraph("Adopt in this order — highest value-to-effort first:", body))

check = [
    ("Week 1 habits (free, huge value)",
     ["Write an ADR whenever you choose between two real options (half a page each).",
      "Git hygiene: feature branches even solo, meaningful commits, never commit to main directly.",
      "Add .env.example; keep all config environment-driven (already largely done here)."]),
    ("First sprint additions",
     ["Set up CI on day one: ruff + mypy + pytest, including a postgres service container for -m 'not db' vs full runs.",
       "Introduce Alembic before writing any table DDL; treat schema like code.",
       "Make seeds idempotent scripts (python -m app.seed), not one-off generation events."]),
    ("Before first real users",
     ["Playwright E2E covering the login -> hierarchy -> dashboard journey (Playwright MCP now configured for this repo).",
       "Structured logging + a /health endpoint; log query timings for the readings range queries.",
       "Freshness check: a scheduled job/test that fails loudly when latest reading age exceeds threshold."]),
    ("When it becomes multi-user/production",
     ["Replace demo auth behind the same interface (already isolated - good); add roles/permissions.",
       "Partition or index-partition the readings table by time; set a retention policy.",
       "Deploy staging + prod from one IaC definition; document rollback; write the runbook."]),
]
for title, items in check:
    block = [Paragraph(title, h2)]
    for it in items:
        block.append(Paragraph(it, bullet, bulletText="[ ]"))
    story.append(KeepTogether(block))

story.append(Paragraph("7. Mindset Shifts That Matter Most", h1))
shifts = [
    ("From", "To"),
    ("'It works after I ran the tests.'",
     "'CI proved it works, on every push, forever.'"),
    ("'The schema is what I created.'",
     "'The schema evolves through reviewed, reversible migrations.'"),
    ("'I'll add logging if there's a bug.'",
     "'Observability exists so bugs announce themselves.'"),
    ("'Done means features complete.'",
     "'Done means deployed, monitored, documented, and demoed to a user.'"),
    ("'I build, therefore I know it's right.'",
     "'Someone/something independent reviews every change.'"),
]
tm = Table([[Paragraph(c, cellh if i == 0 else cell) for c in row] for i, row in enumerate(shifts)],
           colWidths=[88*mm, 92*mm])
mc = [
    ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dbdb")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]
for i in range(1, len(shifts)):
    mc.append(("BACKGROUND", (0, i), (-1, i), ROW_B if i % 2 == 0 else ROW_A))
tm.setStyle(TableStyle(mc))
story.append(tm)

story.append(Spacer(1, 6*mm))
story.append(Paragraph(
    "Note: this analysis reflects a solo, AI-assisted development build. Several 'gaps' "
    "(code review, sprints, stakeholder demos) are team rituals - their solo equivalents "
    "(self-review with fresh eyes, timeboxed increments, user feedback sessions) capture most of the benefit.",
    small))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(20*mm, 12*mm, "Powerplant Dashboard - Workflow Analysis")
    canvas.drawRightString(A4[0]-20*mm, 12*mm, f"Page {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=18*mm, bottomMargin=20*mm,
                        title="Professional Workflow vs This Project")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("written:", OUT)
