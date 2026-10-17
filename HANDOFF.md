# NBOT V6 — living cross-chat HANDOFF and continuation prompt

**Maintained:** October 17, 2026, Asia/Kolkata. **Source of truth for resuming work:** this file, the branch's [ROADMAP.md](ROADMAP.md), [M2_EVIDENCE.md](M2_EVIDENCE.md), [M2R_RESEARCH.md](M2R_RESEARCH.md), and the latest evidence. Always verify the *current* repository head / latest run before using a result; this file may lag a commit.

## Owner's standing instruction — KEEP THIS HANDOFF CURRENT

**Whenever a conversation materially changes NBOT V6** (code, configuration, historical results, test conclusions, safety status, decisions, roadmap, pending experiment or next-action priorities), **update this GitHub HANDOFF.md during the same work session**, preferably in the same series of commits. Update the **continuation prompt at the bottom** too so a fresh chat can resume without asking the owner to reconstruct the project. Tick only truly completed [ROADMAP.md](ROADMAP.md) items; note failures and unresolved blockers explicitly. Also update relevant detailed evidence and draft PR #50 where applicable. **If a future chat lacks GitHub access, say so; do not falsely claim the handoff was updated.**

This root HANDOFF.md was **created on October 17, 2026** because the active V6 prototype branch did not yet contain a GitHub handoff file. Future updates should **modify this same file**, not create fragmented new chat notes.

## 1. Project and hard safety limits

- Private owner repo: **samqju/Nbot**. Dedicated unmerged branch: **prototype/v6-freqtrade-freqai-20261016**. [Draft PR #50](https://github.com/samqju/Nbot/pull/50), **keep DRAFT and do NOT merge** without owner approval.
- V6 uses Freqtrade 2026.9 + FreqAI LightGBMRegressor, Binance USDT-M futures **PUBLIC historical candles**, 5m with 1h context. Owner-selected fixed 25-pair historical universe in [user_data/config.json](user_data/config.json). No need for exchange credentials or order placement.
- Authorized isolated 8GB Ubuntu research VPS access through the connected Windows laptop **Sameer-Laptop**, saved PuTTY session **8GB-Observation**. Existing research checkout: **/root/nbot-v6-m1-20261016/source**; research Docker containers are transient. Never copy private keys or obtain API keys. The owner has a *separate legacy V5 fleet*; NEVER access, alter, restart, migrate or configure V5 machines or services.
- Normal V6 historical tests use **100,000 simulated USDT initial wallet, 1,000-USDT stakes, 1× leverage and ONE concurrent position**. That is a historical **test control**, **not** a change to the owner's intended M4 virtual paper design.
- **M4 paper (not authorized to start):** eventually allow **up to 20 simulated positions concurrently**, conditioned on valid opportunities, exposure/margin/risk limits. Do not commission an unattended paper daemon, or silently treat the 1-slot historical control as the intended paper capacity.
- **M5A intelligent 8-hour universe selector:** still required and **UNBUILT**. Reconsider market candidates roughly every **8 hours**, select up to **25 eligible/liquid/cost-efficient/model-ready Binance USDT-M markets**, control churn, protect existing positions; no guarantee of profits.
- **M7 live real money PERMANENTLY LOCKED** until a *new separate explicit owner approval* and all research and safety gates. Never start real orders, open exchange API, expose credentials, activate automatic promotion or merge the draft PR.
- **M2 trading release / economic quality = NO-GO**. M2R offline experimental code is *authorized for research only*. **M3 multi-regime milestone NOT STARTED / not accepted**; do not relabel existing preliminary M2R trials as M3 certification.

## 2. Completed research and key lessons (all results SIMULATED, not actual fills)

### M1 technical gate (passed infrastructure, failed to show profits)
- 25/25 Binance historical OHLCV/1h+mark/funding source checks, isolated 8GB VPS, real LightGBM fit and engine integration succeeded.
- October **1–7, 2026** old price-AI: **34 trades, −135.640 USDT**. Frozen non-AI EMA setup: **31 trades, +169.849 USDT**. A positive week was NOT evidence of dependable profitability.

### M2 real full-month September 2026
- Downloaded July/August warmup/training history, audited 25/25, ran **125 chronological AI model fits** (25 pairs × 5 weekly windows). All strategies historical max-one-position.
- September **1–30** original price-AI **137 trades, −444.980 USDT**; original no-ML **163 trades, −242.894 USDT**; **NO TRADE 0**. Doubling historical engine fee to 0.10% each side worsened results to AI **−576.688**, no-ML **−388.318 USDT**. No-ML was exposed **99.641% of September**.
- [Full September evidence](evidence/m2/2026-10-17-september-full-month-analysis.md), [machine-readable report](evidence/m2/2026-10-17-september-30day-comparison.json), [M2 general evaluation](M2_EVIDENCE.md).
- Initial original-AI lookahead-analysis flagged **\`has_bias=Yes\`** on prediction/indicator/entry/exit columns. BTC and ETH as-of training comparisons passed, but **all-pair and native FreqAI label-boundary leakage still NOT cleared**.
- Real Binance archived 30-second historic depth data exist, but exact bid/ask, queue/fill execution, stop slippage are **not fully observable** for 2026; **17 of 130** examined October entry/exit events had stale/absent usable depth. Two **~0.10-USDT** external vs Freqtrade funding mismatches at Sep-to-Oct forced trade closures remain unexplained. Do not invent precise historical execution prices or wave away discrepancies.

### M2R — owner-approved after-cost trade learning and bounded strategy research
Owner expects FreqAI to learn **which complete trade setups win after costs and risk**; model should be able to choose **NO TRADE**, and later *safely* select among independently tested strategies. FreqAI is a **framework**, not an automatic PnL-aware strategist: must supply suitable features, trade-level labels, controls, cost assumptions and chronological evaluation.

**Implemented prototype:**
- [After-cost opportunity label library](user_data/strategies/nbot_trade_outcome.py): breakout LONG/SHORT and EMA pullback LONG/SHORT; causal technical setups; next 5-minute candle OPEN hypothetical entry; 12-bar (60m) holding limit, 2% stop, 5% target, stop-first ambiguous OHLC; presumed fee **0.05% each side**, extra slippage **0.05% each side** and funding reserve **0.01% total** = **0.21% assumed modeled roundtrip cost**. This is a **training label model**, not real fills.
- **29,033** overlapping hypothetical complete-trade opportunities in September on all 25 markets, **32.332%** with positive after-cost label. Individual overlapping examples are **not** actual independent portfolio trades. [September labels](evidence/m2r/2026-10-17-september-all25-opportunity-labels.json).
- [Combined historical-only after-cost strategy](user_data/strategies/NbotV6TradeOutcomeResearch.py), [separate breakout/pullback FreqAI models](user_data/strategies/NbotV6FamilyResearch.py), [matched 60-minute no-AI controls](user_data/strategies/NbotV6MatchedNoMLResearch.py), [offline deterministic abstaining router](user_data/strategies/nbot_strategy_router.py), [chronological purge helper](scripts/m2r_purged_split.py). All **offline / historical only**: router is **NOT connected** to active Freqtrade trading, and models **not promoted**.
- September **1–30** combined after-cost AI **125 real fits, 332 actual backtested entries/exits, −442.471 simulated USDT**. This remains a loss and barely differs from original price-AI −444.980.
- **October 8–15, 2026** (pre-registered before this second-stage trial, now already inspected) **8-day** official 25-coin portfolio backtests, max 1 position, 0.05% engine fee per side:

| Model / reference | Historical closed trades | Simulated net P&L USDT |
|---|---:|---:|
| Original price-only FreqAI | 45 | **+205.976** |
| New after-cost pullback-only FreqAI | 68 | **+146.237** |
| New after-cost combined FreqAI | 98 | **+113.046** |
| New after-cost breakout-only FreqAI | 83 | **+62.552** |
| Original non-AI baseline (its original different exits) | 52 | **+24.135** |
| Matched 60min breakout no-AI | 178 | **−34.227** |
| Matched 60min pullback no-AI | 177 | **−88.489** |
| Matched 60min combined no-AI | 189 | **−141.359** |
| NO TRADE | 0 | **0** |

- [Predeclared comparison](evidence/m2r/2026-10-17-preregistered-setup-comparison.md); [official results for all 8 variants](evidence/m2r/2026-10-17-oct08-16-eight-strategy-official-backtests.json); [human-readable detailed research results](evidence/m2r/2026-10-17-aftercost-model-learning-results.md).
- Actual **saved FreqAI forecast** and counterfactual label comparison (October 8–15) indicates *selective learning*: combined model selected **302 of 7,732** overlapping historical opportunities; selected hypotheticals had **45.364%** positive vs **33.148%** across all, with only **+0.0153% mean net label return** vs **−0.143%** baseline. Breakout-only selected **235/4,295** (43.404% selected positive vs 34.109% all); pullback-only **154/3,437** (44.156% selected positive vs 31.946% all). These are **candidate forecasts and hindsight evaluation outcomes, NOT executed trades, wallet returns or certain profits**.
- **Costs threaten the model's apparent gain:** additional *hypothetical* fixed-trade **10 basis-point roundtrip** haircut turns Oct 8–15 combined after-cost PnL **+113.046 → +15.112 USDT**; extra **15bps → −33.855 USDT**. At extra **25bps**, **all** new after-cost variants turn negative, while original price-AI remains positive on this one period. [Cost sensitivity](evidence/m2r/2026-10-17-oct08-16-full-cost-sensitivity.json). The new model's hypothetical label already reserved slippage and funding, but the Freqtrade engine's historical PnL is **not** a verified real-fill return.
- **Decision:** The new after-cost models sometimes filter the matched no-AI entries advantageously but **have NOT beaten the original price-AI on the October 8–15 official backtest**, lost money in September, and are too cost-sensitive to promote. **NO-GO; NO TRADE remains acceptable.** No autopilot switcher yet.

## 3. Next steps — agreed priorities in order

**The user asked, “What should be next step?”** Answer: prioritize scientific reliability and an actual durable after-cost advantage, not immediate automatic switching.

1. **Research gate / MOST URGENT:** investigate original FreqAI **\`has_bias=Yes\`** warning and explicitly verify / implement **12-bar future-outcome label purging at each actual FreqAI training cutoff** (the offline helper alone is NOT integrated into model training). Audit data ordering, start/end alignment, forward-label indexing and stale-model behavior. Re-run original and new model as-of prefix tests; keep models blocked if unresolved.
2. **Comparable evaluation:** repeat separate breakout/pullback/combined LightGBM vs **matched-exit** no-AI controls, original price-AI and NO TRADE on several **new, predeclared, previously UNSEEN** market periods and varied conditions. September, Oct 1–7 and Oct 8–15 are **already explored and cannot be described as fresh blind future validation**. If earlier untouched dates are chosen, fetch enough *prior* market history for 30-day model fitting and warmup, preserve chronological boundaries.
3. **Actual model quality:** evaluate prediction calibration, abstention rate, trade-level statistical uncertainty, PnL concentration, long vs short, stale prediction handling and per-setup sample sizes; do not maximize backtest PnL by trying arbitrary thresholds and reporting only the winner. Evidence from one week can be noisy.
4. **Execution economics:** charge defensible, realistic conservative cost ranges and funding at trade time. Seek independently measured prospective spread/depth/stop slippage before any paper-trading acceptance; hypothetical 10–25bp stress cannot prove real fills. Treat default decision as NO TRADE if the estimated edge cannot cover uncertain costs.
5. **Research-only strategy selector:** once the above checks pass, feed candidate-specific as-of forecasts into the already-built offline router; test decision conflicts, timing, model readiness, risk, universe rotation interactions, and non-overlapping portfolio trade accounting. **Do not** enable automatic live/paper switching, model autopromotion or trades without separate owner milestone approval.
6. **Owner's required future scope:** M5A *every 8h, up to 25 suitable markets*; M4 **up to 20 simultaneous paper virtual positions**, gated and not started. M7 live locked. V5 untouched.
7. Before doing substantial new work, inspect the [ROADMAP detailed checkboxes](ROADMAP.md), [M2R research findings](M2R_RESEARCH.md), [draft PR #50](https://github.com/samqju/Nbot/pull/50), CI status and current VPS. Update **this HANDOFF.md and continuation prompt** every time work materially changes state.

## 4. Exact operational context (only if computer/repo tools are connected and user authorizes research)

- User controls the **Sameer-Laptop** Remote Desktop Commander device, saved PuTTY profile **8GB-Observation**; SSH session to the **separate authorized V6 research VPS only**. Do **not** ask the user for passwords, keys, Binance credentials or V5 access.
- On VPS: \`cd /root/nbot-v6-m1-20261016/source\`; all source changes must originate on the **prototype branch**. \`git pull --ff-only\` is used before bounded tests. V6 Docker image: \`freqtradeorg/freqtrade:stable_freqai\`; bounded \`docker run --rm --cpus=2 --memory=6g ... backtesting\`, **NEVER \`trade\`**. Original 8GB VPS still has ample RAM/disk according to prior checks; don't promise no memory spikes without monitoring.
- Repro archives / ML models reside under \`user_data/backtest_results\` and \`user_data/models\`; detailed logs outside source under \`/root/nbot-v6-m1-20261016\`. Committing large model binaries is not needed. Distinct experiment \`freqai.identifier\` prevents reuse; never silently change fixed historic evidence.
- For any new model or experiment, **pre-register dates, comparison methods, costs and acceptance** in GitHub BEFORE viewing its results; training and test dates must not overlap through a future-label horizon.
- GitHub-specific ability: connected GitHub plugin can fetch and update files / draft PR metadata. Work/desktop connectors may be needed for shell-based VPS tests. Respect the user's preference not to hand work off to Work mode if they have already declined that option.
- Communication preference: **simple clear English** and direct answers, no unproven claims of profitability, no hype, no unexplained jargon. Explain AI "learning" as fitted patterns and prospective forecasts, not memory of its own prior order wins unless its training target explicitly includes that information.
- **HANDOFF maintenance protocol:** at end of each material code/test decision, update (1) \`HANDOFF.md\` (results + current blockers + next steps + prompt below), (2) affected ROADMAP checkboxes, (3) relevant machine/human evidence, (4) draft PR description when material. Do not report an update unless GitHub confirms its commit.

---

## 5. COPY/PASTE PROMPT FOR A FRESH CHAT (update this whenever the state changes)

> Continue my private **NBOT V6** trading research project from our GitHub **samqju/Nbot**, branch **prototype/v6-freqtrade-freqai-20261016**, draft **PR #50**. First read **HANDOFF.md** (this file), **ROADMAP.md**, **M2_EVIDENCE.md**, **M2R_RESEARCH.md** and the October 17 M2R evaluation evidence in \`evidence/m2r/\` from the current branch, then verify the latest branch head and actual CI/test state. **Keep GitHub HANDOFF.md updated after every material change, including updating THIS continuation prompt for the next new chat.**
>
> My objective is not predicting price movements alone: I want FreqAI/LightGBM to learn **which complete breakout/pullback trades have a worthwhile outcome AFTER fees, slippage and risk**, including trading opportunities rejected by the current one-position bot. I ultimately want the AI to decide between approved strategies **or NO TRADE**. **Do not assume FreqAI automatically learns PnL or strategy switching without specifically programmed targets and tested governance.**
>
> Historical work completed: 25-pair M1 technical pass but the first Oct week price-AI lost **−135.640 USDT**. Full September original AI **−444.980**, non-ML **−242.894**. New after-cost AI completed **125 September model fits**, 332 trades **−442.471 USDT**. **October 8–15 eight-day** results: original price-AI **+205.976 USDT** (45 trades), new combined after-cost AI **+113.046** (98), breakout-only **+62.552** (83), pullback-only **+146.237** (68), original no-ML **+24.135** (52); matched no-AI 60min controls lost (combined **−141.359**, breakout **−34.227**, pullback **−88.489**); NO TRADE **0**. Forecast selection is better than raw candidate outcomes in this small sample (combined 302/7732 selected, 45.364% positive vs 33.148% raw), **BUT** gain is fragile: +113.046 combined becomes **+15.112** at extra 10bps hypothetical roundtrip fill cost, and **−33.855** at extra 15bps. No proof of durable real trading edge.
>
> **IMMEDIATE NEXT TASK:** Resolve the official FreqAI \`has_bias=Yes\` integrity warning and prove/implement **purging of future complete-trade labels across EVERY native LightGBM training cutoff**. Then design and preregister *new untouched* chronological multi-regime tests, matched after-cost AI vs no-AI exit controls vs price-AI and NO TRADE, calibration and realistic costs, before any automatic strategy switch. Use September and Oct 1–15 only as already-seen research, never blind final proof. Document failures and update checklists honestly. The M2 release remains **NO-GO**, M3 **NOT STARTED**, and the new router is **OFFLINE ONLY**.
>
> **Safety:** Work only in the isolated V6 research branch and owner-approved 8GB VPS via connected Sameer-Laptop saved PuTTY session **8GB-Observation** if connected. **Never touch V5**, never request/expose keys, never enable unattended M4 paper or M7 live money, never merge PR without approval. Keep required M5A **8-hour intelligent selection of up to 25 coins** and M4 **up to 20 simultaneous virtual paper positions** on roadmap, both currently inactive. Run bounded \`backtesting\` experiments only. Use simple English in replies and tell me exactly what passed, failed and remains unverified.

