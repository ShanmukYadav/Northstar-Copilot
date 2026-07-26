"""Generate FINAL_SUBMISSION_Northstar.pdf on Desktop and in docs/."""
from pathlib import Path
from fpdf import FPDF

OUT_DESKTOP = Path(r"C:\Users\autumn\OneDrive\Desktop\FINAL_SUBMISSION_Northstar.pdf")
OUT_DOCS = Path(r"C:\Users\autumn\OneDrive\Desktop\northstar-copilot\docs\FINAL_SUBMISSION.pdf")


class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, "Northstar Insight Copilot - Final Submission", align="L")
        self.ln(8)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")

    def h1(self, t):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(20, 40, 70)
        self.multi_cell(0, 8, t)
        self.ln(2)

    def h2(self, t):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(25, 55, 95)
        self.multi_cell(0, 7, t)
        self.ln(1)

    def h3(self, t):
        self.ln(1)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6, t)
        self.ln(0.5)

    def body(self, t):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 5.2, t)
        self.ln(0.5)

    def bold(self, t):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 5.2, t)
        self.ln(0.3)

    def bullet(self, t):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 5.2, f"  -  {t}")

    def small(self, t):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 4.8, t)
        self.ln(0.5)

    def table(self, headers, rows, col_w=None):
        if col_w is None:
            col_w = [self.epw / len(headers)] * len(headers)
        line_h = 5

        def draw_header():
            self.set_font("Helvetica", "B", 8)
            self.set_fill_color(30, 60, 100)
            self.set_text_color(255, 255, 255)
            for i, h in enumerate(headers):
                self.cell(col_w[i], 6.5, h, border=1, fill=True, align="C")
            self.ln()
            self.set_font("Helvetica", "", 8)
            self.set_text_color(20, 20, 20)

        draw_header()
        fill = False
        for row in rows:
            # measure height
            heights = []
            x0, y0 = self.get_x(), self.get_y()
            for i, cell in enumerate(row):
                # simulate
                lines = self.multi_cell(
                    col_w[i], line_h, str(cell), border=0, dry_run=True, output="LINES"
                )
                heights.append(len(lines) * line_h + 1)
            row_h = max(heights) if heights else line_h
            if y0 + row_h > self.h - 15:
                self.add_page()
                draw_header()
                y0 = self.get_y()
                x0 = self.get_x()
            if fill:
                self.set_fill_color(240, 244, 248)
            else:
                self.set_fill_color(255, 255, 255)
            for i in range(len(headers)):
                self.set_xy(x0 + sum(col_w[:i]), y0)
                self.cell(col_w[i], row_h, "", border=1, fill=True)
            for i, cell in enumerate(row):
                self.set_xy(x0 + sum(col_w[:i]) + 0.5, y0 + 0.5)
                self.multi_cell(col_w[i] - 1, line_h, str(cell), border=0)
            self.set_y(y0 + row_h)
            fill = not fill
        self.set_x(self.l_margin)
        self.ln(2)


def build() -> PDF:
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_margins(14, 14, 14)

    pdf.h1("Final Project Submission")
    pdf.body("Futurense AI Clinic  |  Capstone Project 05")
    pdf.body("Client persona: Northstar Analytics")
    pdf.ln(2)

    pdf.h2("1. Project Title")
    pdf.bold("Northstar Autonomous Analytics and Insight Copilot")
    pdf.body(
        "Agentic analytics system: plain-language business questions over Olist "
        "e-commerce data, producing verified SQL and plain-language insight with query exposure."
    )
    pdf.body("Short name: Northstar Insight Copilot")

    pdf.h2("2. Names of All Team Members")
    pdf.table(
        ["#", "Name", "Git identity", "Primary focus"],
        [
            ["1", "Ankit", "ankit-2244", "Product & discovery (Sprint 0)"],
            ["2", "Vishal", "vicodwer", "Design, data, core pipeline (Sprints 1-2)"],
            ["3", "Shanmuk", "ShanmukYadav", "Scale, gateway, operate & present (Sprints 3-4)"],
        ],
        col_w=[10, 28, 35, 107],
    )
    pdf.body("Squad size: 3")
    pdf.small(
        "Contributions follow git commit history on main "
        "(authors ankit-2244, vicodwer, ShanmukYadav)."
    )

    pdf.h2("3. Sprint Updates")
    pdf.table(
        ["Sprint", "Focus", "Status", "Led in git"],
        [
            ["Sprint 0", "Discover & Define", "Complete", "Ankit"],
            ["Sprint 1", "Design & De-risk", "Complete", "Vishal"],
            ["Sprint 2", "Build the Core", "Complete", "Vishal"],
            ["Sprint 3", "Harden, Scale, Optimize", "Complete", "Shanmuk"],
            ["Sprint 4", "Verify, Operate, Present", "Complete", "Shanmuk"],
        ],
        col_w=[28, 55, 30, 67],
    )

    pdf.h3("Sprint 0 - Discover & Define (Ankit)")
    pdf.bullet("Discovery brief, personas, probing questions")
    pdf.bullet("PRD v1: problem, scope, metrics, NFRs")
    pdf.bullet("Evaluation plan, risk register v1, team charter")
    pdf.small(
        "Evidence: docs/prd.md, docs/stage1_discover/, docs/stage2_define_evalplan/, "
        "docs/stage4_risk/, docs/team_charter.md"
    )

    pdf.h3("Sprint 1 - Design & De-risk (Vishal)")
    pdf.bullet("Architecture, orchestration decision, agent contracts, verifier contract")
    pdf.bullet("DuckDB sandbox, synthetic data pipeline, golden set seed, eval harness")
    pdf.bullet("Riskiest-assumption spike (Verifier)")
    pdf.small(
        "Evidence: docs/stage3_design/, src/sandbox/, src/synthetic/, src/spike/, evals/"
    )

    pdf.h3("Sprint 2 - Build the Core (Vishal)")
    pdf.bullet("Live agents: Router, Query Writer, Verifier, Narrator")
    pdf.bullet("End-to-end pipeline with retry-once")
    pdf.bullet("First eval scripts (router, query writer, full pipeline)")
    pdf.small("Evidence: src/agents/, src/verifier/, src/pipeline.py, src/eval/eval_*.py")

    pdf.h3("Sprint 3 - Harden, Scale, Optimize (Shanmuk)")
    pdf.bullet("LLM gateway, cache, agent registry")
    pdf.bullet("Clarifier + Planner agents")
    pdf.bullet("Semantic result matching, regression tests")
    pdf.bullet("A/B narrator harness, burst load, DSPy/prompt scaffold")
    pdf.small("Evidence: src/gateway/, src/registry/, clarifier/planner, tests/, eval harnesses")

    pdf.h3("Sprint 4 - Verify, Operate, Present (Shanmuk)")
    pdf.bullet("FastAPI + web UI")
    pdf.bullet("Ops runbook, SLOs, canary/rollback")
    pdf.bullet("Baseline benchmark vs single-LLM path")
    pdf.bullet("Presentation script, viva prep, close-out docs")
    pdf.small("Evidence: src/api/, ops/, docs/sprint4/, baseline_benchmark.py")

    pdf.h3("Quality snapshot (system)")
    pdf.table(
        ["Metric", "Value"],
        [
            ["Pipeline accuracy (golden set)", "18/18 (100%) semantic match"],
            ["Avg cost / question", "~$0.003"],
            ["Latency p50 / p95 (sequential)", "~5.5s / 8.4s"],
            ["Burst (10 concurrent)", "10/10 answered"],
        ],
        col_w=[90, 90],
    )

    pdf.h2("4. Latest Project Status")
    pdf.table(
        ["Dimension", "Status"],
        [
            ["Overall", "Sprints 0-4 complete"],
            ["Demo", "Local FastAPI UI working (uvicorn src.api.app:app --port 8000)"],
            ["Core quality", "Golden-set 18/18; clarify & refuse working"],
            ["Data", "Olist in DuckDB (read-only); rebuild via build_db.py"],
            ["Cloud", "Docker/AWS pilot planned (college budget <= Rs 2000)"],
            ["Presentation", "Script ready: docs/sprint4/presentation_20min.md"],
        ],
        col_w=[40, 140],
    )

    pdf.h3("Runtime architecture")
    pdf.body(
        "User (UI/API) -> FastAPI -> LLM Gateway -> Router -> "
        "(refuse | Clarifier | Planner | standard) -> Query Writer -> "
        "Verifier (retry-once) -> Narrator -> Answer + SQL + cost/latency"
    )

    pdf.h3("How to run")
    for line in [
        "1. Clone the GitHub repository",
        "2. Create .env with OPENROUTER_API_KEY=...",
        "3. pip install -r requirements.txt",
        "4. python src/sandbox/build_db.py  (if sandbox.duckdb missing)",
        "5. uvicorn src.api.app:app --host 0.0.0.0 --port 8000",
        "6. Open http://localhost:8000/",
    ]:
        pdf.bullet(line)

    pdf.h2("5. Individual Contribution of Each Team Member")
    pdf.small("Based on git authors and files in each sprint commit.")

    pdf.h3("Ankit (ankit-2244)")
    pdf.bullet("Product/discovery: discovery brief, personas, problem framing")
    pdf.bullet("PRD: problem, users, scope, metrics, NFRs")
    pdf.bullet("Planning: evaluation plan, risk register v1, team charter")
    pdf.bullet("Sprint ownership: Sprint 0 commit")

    pdf.h3("Vishal (vicodwer)")
    pdf.bullet("Architecture docs, orchestration decision, agent/verifier contracts")
    pdf.bullet("Data: sandbox builder, synthetic generators, golden/synthetic sets")
    pdf.bullet("Core system: Router, Query Writer, Narrator, Verifier, pipeline")
    pdf.bullet("Eval: eval_pipeline, eval_query_writer, eval_router")
    pdf.bullet("De-risk spike; Sprint ownership: Sprints 1 and 2")

    pdf.h3("Shanmuk (ShanmukYadav)")
    pdf.bullet("LLM gateway, caches, agent registry")
    pdf.bullet("Clarifier, Planner; semantic result_match and pytest suite")
    pdf.bullet("A/B narrator, burst load, DSPy scaffold")
    pdf.bullet("FastAPI API + UI; runbook, SLOs, canary/rollback")
    pdf.bullet("Baseline benchmark, presentation/viva materials; Sprints 3 and 4")

    pdf.h2("6. Collective / Team Contribution")
    pdf.bullet("End-to-end agentic analytics copilot on multi-table Olist data")
    pdf.bullet(
        "Full lifecycle: discover -> define -> design -> risk -> data -> build -> harden -> operate"
    )
    pdf.bullet(
        "Safety: clarify ambiguous questions; refuse destructive intent; deterministic verification"
    )
    pdf.bullet("Measured quality and cost (golden set, cost/latency, burst helper)")
    pdf.bullet("Pilot operate surface: API + UI + ops docs")
    pdf.bullet("Defense materials: presentation script and viva prep")
    pdf.bullet("Shared standards: one repo, no secrets in git, offline unit tests")

    pdf.h2("7. GitHub Repository Link")
    pdf.bold("https://github.com/ShanmukYadav/Northstar-Copilot")
    pdf.body("Default branch: main")

    pdf.h3("Repository contents checklist")
    pdf.table(
        ["Required item", "Location"],
        [
            ["Source code", "src/"],
            ["Documentation", "docs/"],
            ["Datasets", "Olist via rebuild / local data/ (documented)"],
            ["APIs", "src/api/app.py (LLM via OpenRouter)"],
            ["Presentation / reports", "docs/sprint4/, FINAL_SUBMISSION"],
            ["Other", "ops/, evals/, tests/, requirements.txt, README.md"],
        ],
        col_w=[55, 125],
    )
    pdf.body("Never commit .env or API keys.")

    pdf.h2("8. Declaration")
    pdf.body(
        "We confirm that this submission describes Sprints 0-4 on the Northstar Insight "
        "Copilot, that the GitHub repository is the source of truth for code and "
        "documentation, and that secrets are not stored in the repository."
    )
    pdf.ln(3)
    pdf.table(
        ["Role", "Name", "Signature / Date"],
        [
            ["Team member", "Ankit", "____________________"],
            ["Team member", "Vishal", "____________________"],
            ["Team member", "Shanmuk", "____________________"],
        ],
        col_w=[40, 40, 100],
    )
    pdf.ln(4)
    pdf.small(
        "Final submission | Project 05 | Northstar Autonomous Analytics and Insight "
        "Copilot | Team of 3 (Ankit, Vishal, Shanmuk)"
    )
    return pdf


if __name__ == "__main__":
    pdf = build()
    OUT_DESKTOP.parent.mkdir(parents=True, exist_ok=True)
    OUT_DOCS.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT_DESKTOP))
    pdf.output(str(OUT_DOCS))
    print("WROTE", OUT_DESKTOP)
    print("WROTE", OUT_DOCS)
    print("size_bytes", OUT_DESKTOP.stat().st_size)
