## NBOT V7 — Updated Implementation Authorization and Instructions

This message supplements and takes priority over earlier instructions where they differ.

**We are building a complete, production-capable Auto-Learning, Auto-Trading NBOT V7—not a research-only skeleton.**

The historical research laboratory is an independent, removable testing component. The actual architecture must already include the Trading Brain, universe selection, candidate discovery, trade/no-trade decisions, continuous learning, versioned model replacement, paper/live execution interfaces, risk management, persistent outcome memory and recovery controls.

### 1. GitHub requirements

- Continue development in the new **V7 branch** of `samqju/Nbot`.
- Preserve and maintain copies of `V7_ROADMAP.md`, `V7_CHAT_HANDOVER.md` and relevant V7 audit/design documents in the active development branch.
- After EVERY implementation step, experiment, significant result or decision, update the roadmap when needed and append a detailed entry to the chat handover.
- Record commits, implementation state, tests, failed results, blockers, next steps and model versions.
- Selectively reuse audited V3, V4, V5, V5.1 and V6 components. Do not merge entire legacy implementations or rebuild existing functional engines unnecessarily.

### 2. VPS access authorized

You may use this laptop's PuTTY saved session **`8GB-Observation`**, authenticating as `root` through its configured PPK key.

Use the VPS for controlled V7 development, research data acquisition, training and historical evaluation. Check available disk, memory, CPU, installed services and existing processes before operating.

Keep existing NBOT versions isolated. Do not interfere with existing deployments, use real trading credentials, or place real orders without separate explicit authorization.

### 3. Historical research schedule — exact periods

**Period A: January 1 – March 31, 2026**

- Download and validate historical Binance USDT-M perpetual futures data for the historically eligible exchange universe.
- Build timestamp-correct features and labels, including BTC conditions, market structure, strategy-independent and strategy-generated opportunities, MFE, MAE, costs and trade outcomes.
- Train the initial Adaptive Trading Brain A on these three months.
- Freeze Brain A's model, feature schema and decision rules.

**Period B: April 1 – June 30, 2026**

- Run frozen Brain A chronologically without hindsight.
- Record its selected trades, rejected opportunities, missed candidates, outcomes, costs and errors.
- Use the matured historical evidence from January through June to train **Brain B**.
- Freeze Brain B before the third period begins.

**Period C: July 1 – September 30, 2026**

- Evaluate Brain A and Brain B independently under identical historical market conditions, costs and one-slot portfolio restrictions.
- Also evaluate a Brain B1-style same-architecture retraining control if useful, to distinguish the advantage of additional data from the advantage of adaptation.
- Measure ranking quality, profitability, risk, missed opportunities, model calibration and ability to change trading behavior.
- Use the resulting evidence to propose or train **Brain B2 / Brain C** as a subsequent challenger.

**Critical scientific constraint:** Brain B2/C must not be trained using July–September outcomes and then presented as independently successful on July–September. Any such newly trained model needs later unseen historical or prospective data for its own independent assessment.

Because earlier V6 research already examined parts of 2026, clearly classify this nine-month experiment as an initial engineering and adaptive-learning baseline. Preserve a genuinely untouched future evaluation period for subsequent promotion claims.

### 4. What must actually learn

The Trading Brain is the ultimate decision maker. Fixed trading strategies are candidate generators, research teachers and negative controls—not permanent authorities over trade selection.

The brain must learn to:
- Evaluate all eligible Binance futures contracts and select up to 20 promising coins.
- Compare different trading setups and discover opportunities outside fixed strategy templates.
- Adapt its approach to market structure and changing regimes.
- Choose one eligible trade or NO TRADE.
- Learn from selected, rejected and sampled outside-universe opportunities.
- Train challenger models from matured evidence.
- Replace underperforming brain versions only after objective forward evaluation and approved promotion gates.

Maintain strict independent execution/risk protections that cannot be modified by self-learning model behavior.

### 5. Development completion requirements

Build complete modules, integrate them, execute unit and system tests, validate historical data/label correctness, and demonstrate deterministic 3+3+3 replay.

Produce real artifacts: downloaded-data manifests, labeled opportunity datasets, frozen model files, one-slot backtests, Brain A versus Brain B reports, financial results, failed checks and a documented readiness verdict.

**A negative trading result is acceptable as the initial baseline. An incomplete or nonfunctional implementation is not.**

Do not claim profitable AI, proven adaptability or production readiness without supporting evidence.

Keep the reusable actual Auto-Learning and Auto-Trading bot separate from the historical research harness, so the research harness can eventually be retired without rebuilding the trading system.

Proceed with implementation and the authorized VPS historical-data workflow. Maintain the GitHub handover after each meaningful step.
