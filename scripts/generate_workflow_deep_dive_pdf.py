"""Deep-dive PDF: professional engineering workflows for solo/small-team data apps."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    KeepTogether, Preformatted,
)

OUT = r"C:\Users\sikha\Videos\power\powerplant-dashboard\docs\Professional_Workflows_Deep_Dive.pdf"

ACCENT = colors.HexColor("#1a5276")
ACCENT2 = colors.HexColor("#21618c")
LIGHT = colors.HexColor("#eaf2f8")
GREY = colors.HexColor("#5d6d7e")
ROW_B = colors.HexColor("#f4f6f7")
CODE_BG = colors.HexColor("#f8f9f9")
CODE_BORDER = colors.HexColor("#d5dbdb")

def ps(name, **kw):
    base = dict(fontName="Helvetica", fontSize=10, leading=14, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, **base)

h1 = ps("H1", fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=ACCENT, spaceBefore=16, spaceAfter=5)
h2 = ps("H2", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=ACCENT2, spaceBefore=11, spaceAfter=4)
body = ps("Body", spaceAfter=5)
bullet = ps("Bullet", leftIndent=12, bulletIndent=4, spaceAfter=3)
numli = ps("Num", leftIndent=16, bulletIndent=4, spaceAfter=3)
small = ps("Small", fontSize=9, leading=12, textColor=GREY)
quote = ps("Quote", fontName="Helvetica-Oblique", fontSize=10.5, leading=14, textColor=ACCENT, leftIndent=10, spaceAfter=6)
cell = ps("Cell", fontSize=8.6, leading=11.4)
cellh = ps("CellH", fontName="Helvetica-Bold", fontSize=8.8, leading=11.5, textColor=colors.white)
code = ps("Code", fontName="Courier", fontSize=7.8, leading=10.2)

def codeblock(text):
    t = Table([[Preformatted(text.strip("\n"), code)]], colWidths=[170*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CODE_BG),
        ("BOX", (0,0), (-1,-1), 0.5, CODE_BORDER),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    return t

def styled_table(rows, widths, header=True):
    data = [[Paragraph(c, cellh if (header and i == 0) else cell) for c in row]
            for i, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [
        ("GRID", (0,0), (-1,-1), 0.4, CODE_BORDER),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]
    if header:
        cmds.append(("BACKGROUND", (0,0), (-1,0), ACCENT))
        for i in range(1, len(rows)):
            cmds.append(("BACKGROUND", (0,i), (-1,i), ROW_B if i % 2 == 0 else colors.white))
    t.setStyle(TableStyle(cmds))
    return t

story = []

# ================= COVER =================
story.append(Spacer(1, 55*mm))
story.append(Paragraph("Professional Engineering Workflows", ps(
    "CovT", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=ACCENT)))
story.append(Paragraph("A Deep Dive for Solo &amp; Small-Team Builders of Data Applications",
                       ps("CovS", fontName="Helvetica-Bold", fontSize=14, leading=18,
                          textColor=GREY, spaceAfter=16)))
story.append(Paragraph(
    "How professional teams plan, decide, build, verify, ship and operate software like the "
    "<b>Powerplant Dashboard</b> - and how to run those same workflows as a team of one or two. "
    "Synthesised from industry practice: Shippable States Development, Architecture Decision "
    "Records, lean specifications, trunk-based Git workflows, GitHub Actions pipelines, the test "
    "pyramid, zero-downtime database migrations with Alembic, observability and feature flags.", body))
story.append(Spacer(1, 8*mm))
story.append(Paragraph("Companion to 'Building Monitoring Dashboards: How Professionals Do It vs How We Did It' - August 2026", small))
story.append(PageBreak())

# ================= TOC =================
story.append(Paragraph("Contents", h1))
toc = [
    "1. The Core Mental Model: Automate the Roles You Cannot Hire",
    "2. Shippable States Development (SSD): The Solo Methodology",
    "3. The Four-Phase Loop: Capture, Plan, Build, Ship",
    "4. Lean Specifications: The Senior Engineer You Cannot Hire",
    "5. Architecture Decision Records (ADRs)",
    "6. Git Workflow for a Team of One",
    "7. CI/CD Pipeline Design for Python + PostgreSQL",
    "8. The Testing Pyramid in Practice",
    "9. Database Migrations: Alembic Done Professionally",
    "10. Observability & Operations",
    "11. Feature Flags: Decoupling Deploy from Release",
    "12. Rituals: Nightly, Weekly, Monthly",
    "13. Four-Week Adoption Plan",
    "14. Anti-Patterns That Kill Small Projects",
    "15. Applying This to Powerplant Dashboard",
]
for i, item in enumerate(toc, 1):
    story.append(Paragraph(item.replace(". ", ".&nbsp;&nbsp;", 1) if False else f"{i}. {item.split('. ', 1)[1]}", bullet))
story.append(PageBreak())

# ================= 1. Mental model =================
story.append(Paragraph("1. The Core Mental Model: Automate the Roles You Cannot Hire", h1))
story.append(Paragraph(
    "A solo developer is not a developer with a smaller team. A solo developer is the entire "
    "engineering organisation compressed into one person: product manager, QA engineer, DevOps "
    "engineer, release manager, incident responder, and developer - five roles, one brain, one day. "
    "Professionals in large teams survive because each role is a separate person with separate "
    "checkpoints. Your survival strategy must therefore be different: <b>automate each role you "
    "cannot hire for</b>.", body))
story.append(Paragraph(
    "This single idea explains almost every practice in this document:", body))
story.append(styled_table([
    ("Role you cannot hire", "Automation that replaces it"),
    ("QA engineer", "CI runs tests, linters, type checks and smoke checks on every push"),
    ("Release manager", "Feature flags + continuous deployment make releases a flag flip"),
    ("Project manager", "Daily shipping cadence + issue tracker externalise intent"),
    ("Incident responder", "Observability: logs, metrics, alerts announce failures before users do"),
    ("Code reviewer", "Self-review against written specs + AI review + CI gates"),
], [52*mm, 118*mm]))
story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "The way solo projects fail is rarely bad code. It is drowning in the deferred roles: QA "
    "deferred until a customer finds the bug, deployment deferred until 'there's something worth "
    "deploying', planning kept in your head until context switching destroys it. Each deferred role "
    "compounds like debt, and the interest payment arrives at the 90% mark of every project.", body))

# ================= 2. SSD =================
story.append(Paragraph("2. Shippable States Development (SSD)", h1))
story.append(Paragraph(
    "SSD is a methodology designed specifically for developers of one to five. Its core claim: "
    "<b>a development day without a shipping event is a process failure</b>, not a neutral outcome. "
    "Where Continuous Delivery guarantees software <i>can</i> be shipped any time, SSD requires that it "
    "<i>is</i> shipped every working day. The point is not speed for its own sake - it is that "
    "deployment fear is a process smell, and the cure is to deploy more, not less.", body))

story.append(Paragraph("The five laws", h2))
laws = [
    ("Deploy on day one", "'Hello World' reaches production before any business logic exists. If you cannot deploy, you do not have a product - you have a research project."),
    ("Ship every working day", "A bug fix, a flagged feature, a doc update - something ships. Scope reduction is allowed; silence is not."),
    ("CI owns quality", "You cannot QA your own code inside your own head. Green CI plus a disabled flag means you can sleep."),
    ("Hide unfinished work behind flags", "No long-lived branches. Code lands on main invisible to users until the switch flips."),
    ("End every day shippable", "Tests pass, work pushed, CI green, tomorrow's first task identified. Future-you resumes in fifteen minutes."),
]
for title, text in laws:
    story.append(Paragraph(f"<b>{title}.</b> {text}", bullet, bulletText="-"))

story.append(Paragraph("The Ratchet Principle", h2))
story.append(Paragraph(
    "Quality is a ratchet, not a pendulum: every commit must improve the system in some measurable "
    "way, and CI encodes the ratchet so it cannot move backward. No WIP commits on main, no "
    "commented-out code, no 'I'll fix the tests tomorrow'. Reducing scope is engineering judgement; "
    "leaving brokenness behind is not.", body))

story.append(Paragraph("Why the last 10% stops hurting", h2))
story.append(Paragraph(
    "Every project has a hidden second project: integration, error handling, edge cases, deployment, "
    "security hardening - the work nobody budgets for, paid in a crisis at the end. Daily shipping "
    "pays that tax incrementally. By the time features are 'done', the last 10% has already happened.", body))

# ================= 3. Four-phase loop =================
story.append(PageBreak())
story.append(Paragraph("3. The Four-Phase Loop: Capture, Plan, Build, Ship", h1))
story.append(Paragraph(
    "Solo chaos is a systems problem, not a character flaw: no standup forces clarity, no reviewer "
    "catches mistakes, no PM tracks work in flight. The fix is a loop living entirely in Git and a "
    "few Markdown files.", body))

story.append(styled_table([
    ("Phase", "Core habit", "Failure it prevents"),
    ("Capture", "Drop every idea into IDEA.md; triage weekly into GitHub issues", "Lost ideas and impulsive scope creep"),
    ("Plan", "Write a feature brief (goal, scope, non-goals, done-when) before touching a branch", "Three hours building the wrong thing"),
    ("Build", "Conventional commits + breadcrumb note before every context switch", "20-30 min re-orientation tax per return"),
    ("Ship", "Self-review the diff, run the deploy checklist, write a one-line retro note", "11pm production incidents"),
], [22*mm, 82*mm, 66*mm]))

story.append(Paragraph("3.1 Capture", h2))
story.append(Paragraph(
    "When an idea strikes you have three options: ignore it (gone by morning), build it immediately "
    "(scope creep), or park it frictionlessly. Use a third path: a single IDEA.md file. Every Friday, "
    "triage each line with three questions: which project does this belong to? What size is it - "
    "hour, day, sprint? Is it worth an issue? Survivors become GitHub issues with a consistent "
    "template: what and why, in-scope, out-of-scope, done-when, task checklist.", body))
story.append(Paragraph(
    "<b>The out-of-scope line is the most important sentence you will write.</b> 'Not touching the "
    "notification system yet' prevents the 2am realisation that you rebuilt half the app for "
    "something that was never in scope.", quote))

story.append(Paragraph("3.2 Plan", h2))
story.append(Paragraph(
    "Planning is short by design - two to four sentences on the issue before coding starts: Goal "
    "(user's perspective), Scope (specifically included), Non-goals (explicitly deferred), Done-when "
    "(a testable condition). Break the work into checkbox tasks each completable in one session. "
    "Branch names carry context: feat/42-metric-selector.", body))

story.append(Paragraph("3.3 Build", h2))
story.append(Paragraph(
    "Two habits matter more than any tooling. First, conventional commits: imperative subject under "
    "72 characters, one logical change per commit, body explains why (the diff already shows what), "
    "reference the issue ('Closes #42'). Second, the breadcrumb note: before closing the editor or "
    "switching projects, write exactly where you stopped and what comes next. For multi-session "
    "features, open a draft PR early - it gives you a visual diff, a comment thread for decisions, "
    "and proof the work is in progress rather than in limbo.", body))

story.append(Paragraph("3.4 Ship", h2))
story.append(Paragraph(
    "Read your own diff before merging - verify the issue closes, checkboxes are ticked, no debug "
    "code remains, docs reflect changed behaviour. Then run the deploy checklist (section 7.4). "
    "Afterwards write one sentence in RETRO.md. Review it monthly: any note appearing three times is "
    "a process problem worth fixing at the root.", body))

# ================= 4. Lean specs =================
story.append(PageBreak())
story.append(Paragraph("4. Lean Specifications: The Senior Engineer You Cannot Hire", h1))
story.append(Paragraph(
    "Spec-first gets mocked as 'waterfall with markdown' when taken to enterprise extremes. The "
    "useful solo version is minimal: one short spec, one focused build session, one self-review pass "
    "against acceptance criteria. A good spec does four things: names the <b>problem</b> (not the "
    "feature), draws <b>boundaries</b> so neither you nor your AI assistant freelances architecture, "
    "states <b>acceptance criteria</b> that give you a review rubric later, and stays short enough "
    "to rewrite when reality disagrees.", body))

story.append(Paragraph("The six-section spec format", h2))
story.append(styled_table([
    ("Section", "What it does"),
    ("Project overview", "Names the change in plain English"),
    ("Problem statement", "Forces you to say why this exists"),
    ("User stories", "Keeps work tied to real behaviour"),
    ("Components", "Limits which parts of the system may change"),
    ("API / interactions", "Clarifies touchpoints and data flow"),
    ("Edge cases", "Stops happy-path-only construction"),
], [42*mm, 128*mm]))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("Acceptance criteria are boring on purpose", h2))
story.append(Paragraph(
    "They describe visible outcomes, never implementation fantasy. 'Operator selects 7-day range and "
    "KPI strip shows min/max/avg computed over exactly that range' is reviewable. 'Feels smoother' "
    "is not - and unreviewable criteria mean you will review by mood, which is how bugs slip through "
    "and scope expands unchecked.", body))

story.append(Paragraph("Specs and AI assistants", h2))
story.append(Paragraph(
    "When working with an AI coding partner, the spec is the main instruction artifact, not a "
    "background document: hand over the spec file with scope, out-of-scope, and acceptance criteria; "
    "a list of files likely to change; an explicit prohibition on unrelated refactors; and require "
    "the response to map changes back to acceptance criteria. Then run the blunt four-pass review: "
    "<b>behavior</b> (does it do what the spec says?), <b>boundary</b> (did anything outside scope get "
    "touched?), <b>failure</b> (are the listed edge cases handled?), <b>fit</b> (does it match existing "
    "repo patterns?).", body))

# ================= 5. ADRs =================
story.append(Paragraph("5. Architecture Decision Records (ADRs)", h1))
story.append(Paragraph(
    "Code shows what was built; ADRs explain why. Without them, teams re-litigate settled questions, "
    "newcomers guess at rationale, and reversing a decision feels dangerous precisely because nobody "
    "remembers the trade-offs. An ADR is half a page to two pages, written once, stored in "
    "docs/adr/NNNN-short-title.md, numbered sequentially, never deleted - only superseded.", body))

story.append(Paragraph("The lightweight (solo) template", h2))
fields = [
    ("Status", "Proposed | Accepted | Deprecated | Superseded by ADR-XXX"),
    ("Date", "YYYY-MM-DD of last update"),
    ("Context", "2-5 paragraphs: the problem, constraints, forces. Present tense, no solution."),
    ("Decision", "'We will...' - one to three sentences, specific enough to verify"),
    ("Alternatives considered", "At least two, each with pros, cons, and a rejection reason tied to context"),
    ("Consequences", "Both sides: intended outcomes AND accepted trade-offs. An empty negative list means incomplete analysis."),
]
story.append(styled_table(fields, [40*mm, 130*mm]))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("Worked example - from this very project", h2))
story.append(codeblock("""
ADR-001: Use Plotly Dash instead of Streamlit for the dashboard frontend

Status: Accepted      Date: 2026-08-26

Context
  The dashboard must render 8 metrics across a 30-plant hierarchy with
  callback-driven interactivity (metric selector, range filter, drill-down).
  Candidates: Streamlit, Taipy, Plotly Dash. Team constraint: pure Python,
  no JS build toolchain.

Decision
  We will use Plotly Dash with callbacks calling services only; pages and
  components contain no SQL and no domain logic.

Alternatives
  Streamlit - rejected: rerun-whole-script model fights hierarchical
    navigation state; fine-grained callbacks (per-metric updates) awkward.
  Taipy - rejected: smaller ecosystem, less community troubleshooting
    material, hiring pool smaller than Flask/Dash lineage.

Consequences
  + Fine-grained callbacks match our KPI-strip interaction requirements.
  + Flask underneath gives us auth middleware and health endpoints.
  - Verbose layout code compared to Streamlit; needs component reuse
    discipline (see CLAUDE.md rule).
  - Callback sprawl risk; mitigated by keeping callbacks thin
    (gather inputs -> call service -> format outputs).
"""))
story.append(Paragraph(
    "Write the ADR <i>after</i> deciding but while context is fresh; link it from commit messages "
    "('feat(metrics): add oil temperature (ADR-002)'). One decision per record; skip alternatives "
    "only for trivially reversible choices.", body))

# ================= 6. Git =================
story.append(PageBreak())
story.append(Paragraph("6. Git Workflow for a Team of One", h1))
story.append(Paragraph(
    "Gitflow and its ceremony exist to coordinate many contributors. Your actual constraint is "
    "different: no integration lag from others, and your main risk is deploying something broken - "
    "not merge conflicts. The workflow that matches it is <b>trunk-based development with feature "
    "flags</b>: commit directly to main, control visibility with flags.", body))

story.append(Paragraph("When branches ARE right (three cases)", h2))
for b in [
    "Genuine experiments with uncertain outcomes - spikes you might abandon entirely (rewriting a data model, migrating an ORM). The qualifier is 'genuinely do not know'.",
    "Breaking refactors you cannot finish today - parked safely off main, with a personal deadline measured in days, never weeks.",
    "Long-lived deployment variants (e.g. a white-label client branch) - rare, deliberate, visible.",
]:
    story.append(Paragraph(b, bullet, bulletText="-"))
story.append(Paragraph(
    "If you know a change will work and are merely implementing it, that is a feature: main behind a "
    "flag. A branch without a merge deadline on a solo project becomes a context-switching liability.", body))

story.append(Paragraph("Commit discipline", h2))
story.append(Paragraph(
    "First line: imperative verb, <=50 chars, what it does. Blank line. Body: one to three sentences "
    "of <b>why</b>. Make good messages easier than lazy ones with a commit template in .gitconfig, "
    "and keep history linear (pull --rebase) so bisecting a regression months later stays pleasant. "
    "Squash fixups locally before they reach main - the golden rule is: if you would be embarrassed "
    "to show the log to future-you, fix it first.", body))
story.append(codeblock("""
# ~/.gitconfig
[commit]
    template = ~/.gitmessage.txt
[push]
    default = current
[pull]
    rebase = true
[alias]
    lg  = log --oneline --graph --decorate --all
    wip = !git add -A && git commit -m \"WIP\"   # always amend/squash before main

# ~/.gitmessage.txt
# <verb> <subject <=50 chars>
#
# <why this change, 1-3 sentences>
#
# Closes #<issue>
"""))

story.append(Paragraph("Tags as a deployment timeline", h2))
story.append(Paragraph(
    "Tag every deployment with an annotated semantic version (git tag -a v1.4.2 -m \"...\") and "
    "automate the tag push inside your deploy script. Combined with decent messages this gives full "
    "forensic capability for regressions - a chronological log of intentional release points - with "
    "no changelog system required.", body))

# ================= 7. CI/CD =================
story.append(PageBreak())
story.append(Paragraph("7. CI/CD Pipeline Design for Python + PostgreSQL", h1))
story.append(Paragraph(
    "A pipeline does nothing magical - it runs the same commands you could run locally, automatically, "
    "every single time. Design it fail-fast: cheapest checks first, expensive ones only after cheap "
    "ones pass.", body))

story.append(Paragraph("7.1 Stage order (fail-fast)", h2))
stages = [
    ("Stage", "Runs", "Budget", "Tools"),
    ("Lint + format", "every push/PR", "~30 s", "ruff check . && ruff format --check ."),
    ("Type check", "every push/PR", "~1 min", "mypy src/"),
    ("Unit tests", "every push/PR", "< 2 min", "pytest -m 'not db' (pure logic)"),
    ("Integration tests", "every push/PR", "5-10 min", "pytest -m db against ephemeral Postgres service container"),
    ("Migration check", "every PR", "~1 min", "alembic upgrade head on fresh DB; alembic check for drift"),
    ("Build image", "merge to main", "3-5 min", "docker build (multi-stage)"),
    ("Security scan", "merge to main", "~1 min", "pip-audit / trivy; block on CRITICAL/HIGH"),
    ("E2E smoke", "post-deploy", "< 20 min", "Playwright: login -> hierarchy -> device dashboard"),
]
story.append(styled_table(stages, [30*mm, 26*mm, 20*mm, 94*mm]))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("7.2 Integration tests need a disposable Postgres, never a shared one", h2))
story.append(codeblock("""
# .github/workflows/ci.yml  (integration job excerpt)
jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: testdb
          POSTGRES_USER: ci
          POSTGRES_PASSWORD: ci_secret
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Apply migrations then test
        run: |
          alembic upgrade head
          python -m app.seed --small        # fixture-sized seed, not 1.4M rows
          pytest -m db -v
        env:
          DATABASE_URL: postgresql://ci:ci_secret@localhost:5432/testdb
"""))
story.append(Paragraph(
    "Health-check options matter: without them a step can race the database startup and fail "
    "spuriously. Ephemeral containers destroyed after the job replace any shared staging database.", body))

story.append(Paragraph("7.3 Quality gates and reporting", h2))
for g in [
    "--cov-fail-under set ~2% above current baseline, raised gradually (coverage ratchet).",
    "Emit JUnit XML (--junitxml) so every CI platform renders per-test history natively.",
    "Parallel shards via pytest-split when unit suite exceeds ~90 s; balance by recorded durations.",
    "Flaky tests are quarantined immediately: marked, excluded from the gate, tracked with an owner and deadline, rerun on a nightly cron. Never normalize red builds - a red build must mean broken code.",
]:
    story.append(Paragraph(g, bullet, bulletText="-"))

story.append(Paragraph("7.4 The deploy checklist (run before every production push)", h2))
story.append(codeblock("""
[ ] Full build passes locally (zero errors)
[ ] Type check clean;  no debug/print leftovers in diff
[ ] New env vars added to hosting platform; .env.example updated
[ ] No secrets in source or commit history
[ ] Migrations written AND tested locally (upgrade -> downgrade -> upgrade)
[ ] CRITICAL ORDER: apply migrations BEFORE deploying dependent app code
[ ] Post-deploy: health endpoint returns 200; smoke test green
"""))
story.append(Paragraph(
    "The migration-before-code order prevents the most common small-project incident: new code "
    "serving requests against an old schema during the deploy window.", quote))

story.append(Paragraph("7.5 Pre-commit hooks catch problems before commits exist", h2))
story.append(codeblock("""
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.18
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
"""))

# ================= 8. Testing pyramid =================
story.append(PageBreak())
story.append(Paragraph("8. The Testing Pyramid in Practice", h1))
story.append(Paragraph(
    "The pyramid allocates effort by cost: fast cheap tests form the base, slow expensive ones the "
    "apex. Roughly 70% unit, 20% integration, 10% end-to-end. In CI this becomes staged gates that "
    "abort early when the foundation fails.", body))
story.append(styled_table([
    ("Layer", "Share", "Speed", "What it verifies here"),
    ("Unit", "~70%", "ms each", "Timestamp/numeric parsing, KPI math (stats + delta), freshness evaluation, routing/URL parsing, metric configuration"),
    ("Integration", "~20%", "seconds", "Repository range filtering against real Postgres, seed integrity (row counts, coverage, energy monotonicity), service->repo wiring"),
    ("E2E", "~10%", "minutes", "Login -> plants overview -> transformer -> device dashboard; metric switch; range change; freshness badge (Playwright)"),
], [22*mm, 16*mm, 20*mm, 112*mm]))
story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "Behavior-focused tests survive refactors: assert through public interfaces ('operator can view "
    "device KPIs for a 7-day range'), never through internals. Agree the seams before writing tests, "
    "so effort lands on critical paths rather than every edge case.", body))
story.append(Paragraph(
    "Track three numbers over time: flakiness rate, average suite duration, and coverage delta per "
    "change. When duration grows >20% week-over-week, fix parallelism before adding more tests.", body))

# ================= 9. Migrations =================
story.append(Paragraph("9. Database Migrations: Alembic Done Professionally", h1))
story.append(Paragraph(
    "Schema is code: versioned, reviewed, reversible-in-plan, applied identically everywhere. "
    "'Migrations look easy until they hit production' - because production has data, load, and "
    "consequences. The rules below are distilled failure experience from teams running live systems.", body))

rules = [
    ("Wire target_metadata on day one", "env.py must receive Base.metadata after ALL model modules are imported - otherwise autogenerate emits drop_table for every table it cannot see. Verify: python -c \"from app.models import Base; print(sorted(Base.metadata.tables))\"."),
    ("Set naming_convention immediately", "MetaData(naming_convention=...) makes constraint names deterministic: stable diffs, reliable DROP CONSTRAINT, portability. Retrofitting later floods you with rename noise."),
    ("Autogenerate is a draft, never final", "It cannot detect renames (emits destructive drop+create!), misses unnamed/hand-made constraints, and proposes dropping third-party tables. Always review the generated script with git diff before committing."),
    ("Separate DDL from data movement", "Schema-only revisions are fast and predictable; backfills are slow and I/O-bound. Different revisions let ops retry one without the other."),
    ("Never add NOT NULL in one step on live tables", "Postgres validates every row under ACCESS EXCLUSIVE lock - minutes of full outage on millions of rows. Three steps instead: add nullable column -> batched backfill -> CHECK (col IS NOT NULL) NOT VALID, VALIDATE, then SET NOT NULL."),
    ("Create indexes CONCURRENTLY", "postgresql_concurrently=True (runs outside a transaction). A plain CREATE INDEX locks writes for the build duration."),
    ("Set lock_timeout in risky migrations", "op.execute(\"SET lock_timeout = '3s'\") aborts a blocked migration instead of queueing locks for 20 minutes at peak traffic."),
    ("Batch large backfills", "Chunk UPDATEs (10k-50k rows) in a loop; never one UPDATE over millions of rows inside a transaction."),
    ("Test the round trip in CI", "upgrade -> downgrade -> upgrade on a fresh database rejects non-rollbackable migrations before merge. And treat data migrations as forward-only regardless: downgrade() cannot reconstruct transformed rows."),
    ("Expand/Contract for zero downtime", "Add nullable (expand) -> dual-write from new code -> backfill -> switch reads -> drop old column (contract). Old and new code stay valid at every instant."),
]
story.append(styled_table([("Rule", "Details")] + rules, [46*mm, 124*mm]))
story.append(Spacer(1, 3*mm))
story.append(codeblock("""
# Safe rollout of one new NOT NULL column on readings (illustrative)
# Rev 1 (DDL):   op.add_column('readings', sa.Column('quality',
#                    sa.SmallInteger(), nullable=True))
# Rev 2 (data):  batched backfill, chunks of 50k WHERE quality IS NULL
# Rev 3 (DDL):
def upgrade():
    op.execute(\"ALTER TABLE readings ADD CONSTRAINT
                readings_quality_not_null CHECK (quality IS NOT NULL)
                NOT VALID\")
    op.execute(\"SET lock_timeout = '3s'\")
    op.execute(\"ALTER TABLE readings VALIDATE CONSTRAINT
                readings_quality_not_null\")
    op.alter_column('readings', 'quality', nullable=False)
"""))

# ================= 10. Observability =================
story.append(PageBreak())
story.append(Paragraph("10. Observability & Operations", h1))
story.append(Paragraph(
    "Observability exists so bugs announce themselves instead of being discovered by a user staring "
    "at stale data - the worst failure mode for a monitoring product. Three layers suffice for a "
    "small team.", body))

obs = [
    ("Structured logging", "JSON lines with timestamp, level, logger, and a correlation ID per request/callback chain. Friendly message to the user, full stack trace to the log - never the reverse. Log query timings for the readings range queries; they are your performance surface."),
    ("Health & metrics", "A /health endpoint returning DB connectivity + latest reading age. Export latency/error counters; even a single Prometheus gauge for 'minutes since newest reading' turns silent ingestion failure into a visible alert."),
    ("Freshness monitoring", "Scheduled job (or test) that fails loudly when the newest reading exceeds threshold. For a monitoring dashboard this is not optional polish - stale-data blindness destroys the product's entire premise."),
]
story.append(styled_table(obs, [36*mm, 134*mm], header=False))
story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "Dash-specific notes: dev tools (callback graph, in-app errors) are development instruments - "
    "never enable them in production (they display server-side tracebacks, a security vulnerability, "
    "and cost performance). Run production via gunicorn on app.server. Time computationally heavy "
    "callbacks and log the timings; the community-standard pattern is a small decorator around "
    "expensive service calls.", body))

# ================= 11. Feature flags =================
story.append(Paragraph("11. Feature Flags: Decoupling Deploy from Release", h1))
story.append(Paragraph(
    "A flag separates <i>deploying</i> code (merging to main) from <i>releasing</i> it (users seeing "
    "it). This is what makes trunk-based development safe for a team of one: unfinished or risky work "
    "ships dark, enabled internally first, then broadly, then the flag is removed. Rollback of a bad "
    "feature becomes a config flip, not a revert.", body))
story.append(Paragraph(
    "Start embarrassingly simple - an environment variable or JSON file checked through a tiny "
    "helper is genuinely enough; zero-dependency libraries (tiny-flags, toggleflag) add percentage "
    "rollouts and targeting when needed. Discipline matters more than infrastructure:", body))
for f in [
    "Descriptive names (new_kpi_strip, not flag_123) and a description with expected lifetime.",
    "Every flag has a removal plan - a flag with no expiry date becomes permanent complexity debt.",
    "Test both paths: enabled AND disabled states.",
    "Log evaluations sparingly; clean up dead flags in every retrospective.",
]:
    story.append(Paragraph(f, bullet, bulletText="-"))

# ================= 12. Rituals =================
story.append(Paragraph("12. Rituals: Nightly, Weekly, Monthly", h1))
rituals = [
    ("Nightly ritual (5 min)", "All tests pass locally; work committed and pushed; CI green; flags set correctly; breadcrumb note written; tomorrow's first task identified. Future-you resumes cold in fifteen minutes."),
    ("Weekly triage (Fri, 20 min)", "Empty IDEA.md into issues (keep / size / discard); review open branches older than a week - merge, deadline, or delete; skim dependency updates."),
    ("Monthly retro (30 min)", "Read RETRO.md; any note appearing three times becomes a process fix; raise the coverage ratchet one notch; remove expired feature flags; skim error logs for patterns."),
]
story.append(styled_table(rituals, [44*mm, 126*mm], header=False))

# ================= 13. Adoption plan =================
story.append(PageBreak())
story.append(Paragraph("13. Four-Week Adoption Plan", h1))
plan = [
    ("Week 1 - Solve deployment forever", "Stand up the repo on GitHub; wire CI (ruff, mypy, pytest incl. Postgres service container); deploy 'Hello World' of the next app to a real host. Deliverable: green pipeline + live URL. Nothing else this week."),
    ("Week 2 - One vertical slice behind a flag", "Build ONE feature end-to-end (action -> persistence -> UI verification) behind a flag. Write its lean spec and one ADR first. Practice: branch-less flow, conventional commits, self-review against acceptance criteria."),
    ("Week 3 - Establish the rhythm", "Ship something every working day. Add Alembic from the start of any new schema work. Add the deploy checklist and nightly ritual. Start RETRO.md."),
    ("Week 4 - Harden", "Add Playwright smoke journey; add /health + structured logging; add freshness alert if data-ingesting; tune deploy time; remove week-2's flag now that the feature is stable."),
]
rows = [(p[0], p[1]) for p in plan]
story.append(styled_table(rows, [48*mm, 122*mm]))
story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "By day 28 you will have practiced every workflow in this document on a real, deployed, "
    "monitored application - which is the only way any of it becomes habit.", body))

# ================= 14. Anti-patterns =================
story.append(Paragraph("14. Anti-Patterns That Kill Small Projects", h1))
anti = [
    ("'I'll set up deployment when there's something to deploy.'", "There is always something to deploy. Undeployed software is unreality."),
    ("'I'll write tests once the design stabilizes.'", "Design stabilizes BY being tested; without tests you cannot refactor, and an unrefactorable codebase ossifies."),
    ("'I'll merge the branch when it's ready.'", "It is never ready. Land on main behind a flag; iterate invisibly."),
    ("'I'll fix this technical debt later.'", "Later is fiction; the interest payment is your future velocity. Pay incrementally in every commit."),
    ("Manual ALTER TABLE on a shared/dev database", "Schema drift between environments; next autogenerate produces migrations that break cleanly-migrated databases. All DDL goes through Alembic."),
    ("Normalizing red CI", "Once one flaky failure is tolerated, trust in the whole gate collapses. Quarantine explicitly instead."),
    ("Secrets in source or commit history", "Rotation is painful and audit findings are worse. Secrets only via environment/platform secrets."),
    ("Deferring the last 10% (errors, edges, hardening)", "Paid as a crisis at the end instead of incrementally throughout - the classic death march."),
]
story.append(styled_table(anti, [72*mm, 98*mm], header=False))

# ================= 15. Application =================
story.append(Paragraph("15. Applying This to Powerplant Dashboard", h1))
story.append(Paragraph(
    "What already matches professional practice here: documentation-first planning, layered "
    "architecture enforced by rule, environment-driven configuration, isolated demo auth, explicit "
    "scope boundaries, a split pytest suite (pure logic vs DB), seed-integrity testing, and a "
    "user-journey Definition of Done. That is a genuinely strong foundation.", body))
adopt = [
    ("Now (zero new infra)",
     "ADRs for existing big decisions (Dash choice, plant_monitoring schema, synthetic-seed design); IDEA.md + issue templates; conventional commits; breadcrumb notes; RETRO.md; .env.example audit."),
    ("Next sprint",
     "GitHub Actions CI mirroring section 7 (reuse the exact YAML shapes above); pre-commit hooks; alembic introduced BEFORE any further schema change; Playwright MCP smoke journey of login -> hierarchy -> dashboard."),
    ("Before real client data",
     "Migration strategy formalised (naming_convention, round-trip CI test); freshness alert on readings; /health endpoint + structured logging; staging environment spun from the same compose file; retention/partitioning decision for the readings table as ADR."),
]
story.append(styled_table(adopt, [38*mm, 132*mm]))
story.append(Spacer(1, 4*mm))
story.append(Paragraph(
    "Final thought: none of these techniques requires a bigger team or more talent - only the "
    "decision to stop deferring the roles you have been playing badly because they were invisible. "
    "Automate them, and the code you already write well starts compounding instead of eroding.", body))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(20*mm, 12*mm, "Professional Engineering Workflows - Deep Dive")
    canvas.drawRightString(A4[0]-20*mm, 12*mm, f"Page {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=18*mm, bottomMargin=20*mm,
                        title="Professional Engineering Workflows - Deep Dive")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("written:", OUT)
