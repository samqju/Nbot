# NBOT V5.1 — Controlled Startup Owner Checklist & Evidence Register V1.0

**Status: DRAFT / NOT AUTHORIZED FOR STARTUP. No production services started.**  
**Date:** 15 October 2026 (IST)  
**Master plan:** [Controlled Startup & Live-Evidence Validation Master Plan V1.0](NBOT_V5_1_CONTROLLED_STARTUP_AND_LIVE_EVIDENCE_MASTER_PLAN_V1_0.md)  
**Current trusted offline code baseline:** `7ba7abd315fa7fdac5fd0b7babb81d267ffe6348`, 430/430 G0–G11 regressions independently passed on both VPSs.  
**Scope:** Owners can follow this without programming knowledge. Developers/reviewers maintain the detail in the master plan and G4–G10 reports. **This checklist does not create any approval.**

## 1. What the owner must know

**G11 = COMPLETED OFFLINE.** The lab pipeline passes tests but is not a ready-to-activate authentic market service. **G4–G10 genuine acceptance = still OPEN.** We will commission **Observation first**, without account credentials, paper trading or real orders. The owner will be asked for a *separate explicit decision* at each new risk boundary. Do not interpret “the startup checklist is created” as “start now.”

**The safe direction of travel:**

`PREPARE SOURCE-ONLY RUNTIME → OWNER SOURCE APPROVAL → MINIMAL PUBLIC SOURCE → VERIFIED 100/20 + OFF-HOST ORIGINAL EVIDENCE → VIRTUAL RESEARCH → VALIDATED COSTS → SCIENCE → CHAMPION → OWNER PAPER APPROVAL → LATER CHALLENGER PAPER`

At **every arrow**, unresolved evidence means **HOLD**. There is no shortcut from G11 synthetic performance to PAPER, testnet or real trading. G12 is out of scope.

## 2. Owner-facing milestones (check immediately after *independent* proof)

| ID | Milestone owner can understand | Status | Required proof / dependency |
| --- | --- | --- | --- |
| CS-00-A | Confirm actual G11 code and both VPSs still healthy | [ ] | Pinned code SHA, two-host regression, resources, process/service audit |
| CS-00-B | Engineer and test a *separate safe source-only* runner | [ ] | OFF by default, public-only network, no keys, bounded storage and restart HOLD |
| CS-00-C | Choose actual off-host archive, storage budget and retention policy | [ ] | Owner-approved destination and independent restore proof |
| CS-00-D | Agree start/stop, monitoring, hard safety limits and change/rollback steps | [ ] | Documented reviewed thresholds and named escalation/stop operator |
| CS-00-E | Approve CS-00 technical readiness as **not yet running** | [ ] | Independent reviewer signs complete prestart proof pack |
| CS-01-A | **Owner explicitly authorizes a source-only Observation canary** | [ ] | Separate specific written owner approval; public-only, exact SHA and scope |
| CS-01-B | Start one small public source canary and preserve original bytes | [ ] | Timestamped current live read-only public frames and exact provenance |
| CS-01-C | Demonstrate safe source-gap/restart/stop and no trading | [ ] | Independent restart/replay and source HOLD records |
| CS-01-D | Approve expanding source-only cohort when technically safe | [ ] | Canary health, storage and independent reviewer PASS |
| G4-06-A | Verify original TRADE/QUOTE/MARK for **all 20** deep markets | [ ] | Actual 20/20, BTC included, no excused 47 historical trade gaps |
| G4-06-B | Show live feed and 100/20 load will not overwhelm VPSs | [ ] | Measured long-run/bursty p99, CPU/RAM/queue/disk headroom |
| G4-06-C | Independently establish genuine original-source custody | [ ] | TLS/source provenance, clocks, byte-for-byte durable chain, uncertain segments held |
| G4-06-D | Restore **original live** archived evidence on another VPS | [ ] | Independent destination checksum and full replay after controlled outage |
| G4-06-E | Review the entire G4 source gate | [ ] | All G4-06-A to -D individually passed; no source HOLDs disguised |
| CS-03-A | **Owner separately permits virtual Research only** | [ ] | G4 passed, zero actual orders and bounded 40-book admission |
| G5-06-B | Prove honest forward virtual first touch, not estimated fills | [ ] | Verified stream paths, restart/censor/quote uncertainty recorded |
| G5-06-C | Close G5 original Research acceptance | [ ] | G5-06-A already passed offline, B authentic source pass, reviewer signoff |
| G6-06-A | Show actual source-qualified virtual after-cost outcomes | [ ] | Independent quotes, fill model, fees, slippage, fully settled funding |
| G6-06-B | Independently verify live-source archive restore and outage | [ ] | Reconciled original source bytes and cost receipt provenance |
| G6-06-C | Pass prolonged real high-rate storage, recovery and resource checks | [ ] | Real throughput, peak message rates, quotas and rollover |
| G6-06-D | Close G6 economic/original archive acceptance | [ ] | A/B/C genuine pass, G4/G5 complete |
| G7-06-A | Build sufficiently independent *original matured* Research evidence | [ ] | First scientific checkpoint ≥2,000 independently matured genuine observations (currently 0) |
| G7-06-B | Test with unseen real periods, costs, regimes and honest NO_TRADE | [ ] | Independent science report, time embargo, negative evidence retained |
| G7-06-C | Approve genuine Learning science or continue HOLD | [ ] | Independent reviewer scientific gate |
| G8-06-A | Train only from genuine approved original G7 evidence | [ ] | Source/feature/version/holdout lineage, freeze protocol |
| G8-06-B | Independently evaluate first trained Champion candidate | [ ] | Real unseen after-cost advantage, risk, abstentions and no lookahead |
| G8-06-C | Approve first frozen Champion, or retain NO_MODEL | [ ] | Explicit owner and independent scientific qualification |
| CS-07-A | **Owner separately approves PAPER-ONLY Champion trial** | [ ] | G8 first Champion accepted, guardian/risk policy and signed authorization |
| G9-06-B | True model-specific PAPER-only release (not synthetic LAB) | [ ] | Narrow signed owner approval, no real order-capable client |
| G9-06-C | Accept persistent first Champion forward PAPER evaluation | [ ] | Prospectively logged genuine market events, stops, costs, one-paper-position, restarts |
| G9-06-D | Close G9 PAPER gate only after actual trial review | [ ] | Independent review; owner signoff |
| G10-06-A | Collect *another* truly independent new source-qualified cohort | [ ] | New 2,000 review checkpoint and truly frozen distinct Challenger |
| CS-08-A | **Owner separately approves Challenger PAPER contest** | [ ] | Paired common prospective forward protocol with two separate books |
| G10-06-B | Run genuinely fair and audited dual-book PAPER comparison | [ ] | True owner-approved paired events and ≥100 settled PAPER per model when meaningful |
| G10-06-C | Obtain reviewed RETAIN/REJECT/HOLD/PROMOTE decision | [ ] | Separate signed owner authority to change a model, rollback preserved |
| G10-06-D | Close G10 true Challenger PAPER parent | [ ] | All G10 genuine source/science/paper and owner review PASS |
| G12 | **Separate REAL trading project** | [ ] LOCKED | Not requested or included; separate project/safety release required |

**No item above is currently [x] solely because the plan was written.** Keep previously completed offline engineering checkmarks in their existing roadmaps unchanged. The additional CS-* records are commissioning gates, not replacements for G4–G10 checklists.

## 3. Source commissioning observations log (append, do not replace)

| Run ID | Started UTC / local | Stage & exact SHA | Current 100/20 source cohort | Endpoint & source epochs | Owner permission ID | Measured performance/disk | Raw segment/verified archive reference | Gaps and UNKNOWN intervals | PASS / HOLD / FAIL | Independent reviewer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NO RUN YET | — | CS-00 draft only | Not started | No original source | NO AUTHORIZATION | No new runtime measurements | No genuine archive | Prior G4 19/20 and 47 gaps unresolved | HOLD | Not reviewed |

Keep chronological evidence rows, even after a failure. Never overwrite a failed row when a later retest passes.

## 4. Controlled startup and rollback approval card — copy per requested action

**Change/Run ID:** ______  
**Requested action:** ______  
**Exact frozen GitHub SHA and deployed binary/config SHA:** ______  
**Host(s):** Observation / Execution (choose the narrowest appropriate scope)  
**Execution mode:** OFFLINE / PUBLIC_SOURCE_ONLY / VIRTUAL_NO_ORDER / TRUE_PAPER_SIMULATION — **REAL IS NOT AN AVAILABLE CHOICE**  
**Public network endpoints and expected storage:** ______  
**Risk limits / CPU-RAM-disk quotas / stop operator / alerting:** ______  
**Proposed start window (UTC + IST) and stop or review checkpoint:** ______  
**Preflight regression:** Observation ___/430; Execution ___/430, exact SHA ______  
**Independent source/recovery/security reviewer:** ______  
**Predeclared acceptance tests and hard HOLD/rollback triggers:** ______  
**Known unresolved gaps or source epochs:** ______  
**Rollback artifact and archived evidence destination:** ______  
**Specific owner's written approval:** ☐ APPROVE THIS EXACT NARROW ACTION ☐ REJECT ☐ HOLD  
**Owner approval timestamp:** ______  
**Actual operation result:** NOT STARTED / RUNNING PUBLIC SOURCE ONLY / STOPPED / HOLD / FAIL  
**Final evidence link and independent sign-off:** ______  
**Next step requires fresh owner approval?** YES unless a previously signed exact scope explicitly covers it.

### Fail-closed rule

If there is no completed card, independently verified evidence and specific owner authorization, **do not start a service**, do not expand the source cohort, do not activate virtual Research or PAPER and do not touch an exchange account.

## 5. Daily operating review format (only after a future approved start)

- Public 100/20 cohort health, five-minute boundary lateness, BTC and market regime completeness.
- Real original trade/quote/mark rates, sequence ID gaps, disconnected epochs, stale/crossed bid/ask, missing funding and latency, pending vs verified source custody.
- Active virtual Research 0–40, occupied/held/free slots, first-touch vs censored/missing, no heavy Exploration when full.
- Original after-cost matured outcomes (not synthetic), selection denominator and independent effective sample blocks; no forced trades.
- Frozen model identity/authorization, true independent PAPER status only if separately approved; abstentions, risk vetoes, unsettled books and no actual orders.
- Host RAM/CPU, disk quota, compressed segment/compaction integrity, off-host archive acknowledgments, alert and watchdog health.
- Any restart, branch/source SHA change, data gap, tampered file or manual intervention; source epoch and owner's corresponding permission.
- PASS/HOLD/FAIL for each pending G4–G10 microtask, with exact independent evidence link. No automatic checkmarks based on time elapsed.

## 6. How a future chat resumes without losing context

Read, in order:
1. [Most recent V5.1 handoff](NBOT_V5_1_CURRENT_STATUS_NEXT_CHAT_HANDOFF_20261015.md) — **last** section wins over historic intermediate text.
2. [This owner checklist](NBOT_V5_1_CONTROLLED_STARTUP_OWNER_CHECKLIST_AND_EVIDENCE_REGISTER_V1_0.md) — current approval and live-evidence status.
3. [Master commissioning plan](NBOT_V5_1_CONTROLLED_STARTUP_AND_LIVE_EVIDENCE_MASTER_PLAN_V1_0.md) — procedural sequence, safety and acceptance definitions.
4. [Owner Roadmap](NBOT_V5_1_OWNER_ROADMAP_V1_0.md) and [Engineering Roadmap](NBOT_V5_1_ENGINEERING_ROADMAP_V1_0.md) — tiny verified items checked individually; genuine acceptance remains unchecked.
5. Original Complete Product Vision V1.9, G4–G11 detailed evidence reports and the exact latest GitHub code SHA.

**Next *proposed* task:** design and verify CS-00 source-only runtime/service and storage/restore/monitor readiness, OFFLINE. **No commissioning or source collector startup has been authorized.**
