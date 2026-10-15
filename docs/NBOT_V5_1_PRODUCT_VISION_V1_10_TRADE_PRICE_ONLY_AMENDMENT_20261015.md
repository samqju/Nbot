# NBOT V5.1 — Product Vision V1.10: Owner-Approved Trade-Price-Only Market Data Amendment

**Decided:** 15 October 2026. **Applies to:** `nbot-v5.1` after a reviewed, pinned and tested CS-01 release.  
**Original Vision V1.9 remains unchanged**, preserved as historical product baseline. **V1.10 is an explicit scoped amendment** to V1.9 where its bid/ask entry/exit requirement conflicts with the owner's latest decision; all unrelated product invariants still apply.

## Owner's plain-language decision

**Never request or subscribe to bid/ask for the new active NBOT V5.1 source pipeline.** NBOT follows **actual Binance USD-M Futures market TRADE prices** from the public `aggTrade` WebSocket stream; it also reads public `markPrice@1s` when needed for derivative mark/funding context and public exchange/listings, 24h activity and completed five-minute candles for 100-market discovery. No market-depth or bookTicker WebSocket subscription, no REST `ticker/bookTicker` discovery call, no saving ongoing bid/ask receipts for newly collected data.

**Virtual Research and PAPER assumptions:** When a prospectively eligible MARKET entry or exit triggers, **the simulation fills it immediately by convention** at a strictly causal latest trade price adjusted adversely by an independently declared, conservative market execution/spread/slippage cost policy (plus actual modeled taker fees, and attributable funding). NO simulated limit-order queue, touch criterion, or `bid`/`ask` match test. A simulated fill is **not** evidence of an actual achievable or guaranteed Binance fill and must never be called one.

**Modes remain isolated:** VIRTUAL source path and hypothetical fills have **zero exchange order authority**; separately owner-approved PAPER is a simulated book with no orders; future Testnet/REAL would require a real exchange MARKET order, exchange-confirmed fills/quantity/fees, and reconciliation. Neither CS-01 nor this amendment turns those modes on.

## Changes by stage

| Stage | New active behavior | Truth boundary |
|---|---|---|
| G1 | 100 qualified USDT-M perpetuals using exchange information, last-trade/24h turnover/movers and 96+ completed candles; BTC mandatory. **No bid/ask spread screening.** | The old spread-based eligibility proof **does not transfer to the new method**. Source liquidity cannot be called verified from book when no book is fetched. |
| G2 | 100 finalized five-minute candles plus causal time and continuity guards; public REST only for metadata/history | Completed candles cannot reconstruct intrasecond first-touch paths. |
| G3 | 200 coin-direction denominator with 24 original detectors when separately eligible/capacity available; currently initial live 200 detector **skipped** | G3 patterns do not select G4's 20 by popularity; prospective sampling persists. |
| G4 | Exactly 20 deep coins incl BTC; two public WSS combined routes: `aggTrade` and `markPrice@1s`; byte-and-ID-checked trade chronology for source-evidence custody. No bookTicker. | Missing real aggregate `a` IDs, stale trade events, disconnects, incomplete marks and source gaps **HOLD**. Quote age failure from old WSS no longer exists as an active requirement, but old 3-feed historical canary evidence remains historical. |
| G5 | A later **separately approved** Research engine uses original trade price crossings for stop/target order and freezes instant simulated MARKET-entry/exit assumptions. | Current G5 code is **lab-only** and must be migrated/tested before any actual virtual positions; no currently qualified real-source first touch. |
| G6 | Versioned conservative no-book cost model: adverse simulated entry and exit buffer, both taker fees, signed settled funding, threshold/volatility sensitivity; no double-charged spread. | Estimated fill price and quoted cost are modeled; do not label `EXECUTION_VERIFIED`. No silently zero or missing costs. |
| G7–G8 | Training/Champion may only use scientifically eligible *original price-path + versioned cost-assumed simulated-market* outcomes if the new V1.10 validation contract is separately accepted, independently tested, and sufficient prospective observations mature | Earlier V1.9 **quote-proved executable outcome** checkpoint must not be silently reinterpreted, and 0 qualified learning results stays 0 now. |
| G9–G10 | Later owner-authorized Champion/Challenger PAPER fills instantly using the same declared simulated-market cost methodology, independent books, one simulated position/book, loss/risk controls. | Still **PAPER OFF**, no Testnet/REAL. |
| G11–G12 | Lab-only engineering and REAL authorization remain unchanged | Real remains LOCKED. |

## 100→20 choice remains unchanged

G1 selects 100 through turnover/gainer/loser breadth (BTC mandatory); G4 selects 20 through frozen stratum quotas plus deterministic hash rotation, BTC mandatory, **not the 20 best detector matches**. Original eligible names/fair prospective controls and denominator retained. No future/outcome hindsight.

## Cost and scientific confidence — no invented precision

Suggested pure simulation formula for later approved implementation (not live G4):
- LONG BUY = latest observed genuine trade price × (1 + adverse_buffer), LONG SELL = later trade price × (1 - adverse_buffer).
- SHORT SELL = genuine trade price × (1 - adverse_buffer), SHORT BUY = later trade price × (1 + adverse_buffer).
- `adverse_buffer` must be predeclared, defensible, conservative (including unobserved spread/slippage in one cost, **not counted twice**), ideally sensitivity-tested by liquidity/volatility; two-sided taker fee, relevant mark/settled funding separate.
- If trade price missing/stale, trade-ID continuity unknown, stop/target ordering ambiguous, funding cannot be established, or cost assumptions unknown, leave the virtual result **PENDING/HOLD/UNQUALIFIED**; do not make a winning return from thin air.
- For now such labels are `TRADE_ONLY_MARKET_FILL_ASSUMED_MODELED_COST`, never actual exchange fills. Independent G7 acceptance criteria and a release decision need separate evidence. Testnet/Real actual fills must always use exchange results.

## Commissioning contract

**Approved now:** Implement/test this source-only trade-price profile in GitHub and a time-limited **PUBLIC-ONLY CS-01** on Observation VPS. No account credentials, private REST, market/limit orders, PAPER, Testnet, REAL, auto-restart daemon, model promotion or real/virtual scientific claims. Use a **new private diagnostic root**, never overwrite old original captures or first backup. Stop the collector at timer/source HOLD; keep exact SHA and test/receipt evidence. Mark individual roadmaps [x] only when independently demonstrated.

**Engineering reality:** Original V5.1 had direct synchronous 20-market `bookTicker` processing, causing 1,000–1,400 accepted quote messages/s with events approaching a 5,000ms age limit across BTC and other coins. Removing quote from the **actual active** CS-01 stream eliminates that exact quote subscription/overload mechanism, but **does NOT prove the 20-market trade stream has zero gaps, all symbols continuously trade, or full G4 evidence passes**. Re-measure and report the real result.

**Unchanged Vision V1.9:** 40 Research concurrent hypotheses maximum; no automatic profitability from a detector match; prospective, source-traceable, genuinely matured results; Champion/Challenger fairness; separate Execution VPS and account authority; no promised real-money profit.
