# NBOT V5 deployment source reconciliation — 2026-10-14

## Scope and method

Owner requested GitHub reflect the **exact source bytes already installed on both VPSs**, without overwriting newer unreviewed development code or modifying runtime evidence. At approximately 13:16–13:25 UTC on 2026-10-14, source files in each deployed release tree were compared byte-for-byte against Git **tracked blobs** in pinned historical commits. Checks included all tracked regular files, symlink targets, executable permissions, missing files, and unexpected extra files. This is a **source snapshot** check, not a scientific-acceptance or reproducible-runtime-dependencies proof.

| VPS / component | Release directory | Source Git commit and immutable GitHub release branch | Exact matching tracked files | Mismatched/missing |
|---|---|---|---:|---:|
| Observation G1–G3 collector | `/home/ubuntu/nbot_v5_integrated_20261014` | `1e7c090d05dc118b290c764d58c2944f56ad4b3b` — `deploy/v5-observation-g1g2g3-20261014` | 366/366 | 0/0 |
| Observation G4–G6 held research release | `/home/ubuntu/nbot_v5_continuous_release_20261014` | `dc4981c966313e53d996776172dce88eaa79a659` — `deploy/v5-observation-research-held-20261014` | 438/438 | 0/0 |
| Execution G7 locked release | `/home/ubuntu/nbot_v5_continuous_release_20261014` | `33a9c825db304e56628b1959582d350147915e5b` — `deploy/v5-execution-g7-locked-20261014` | 438/438 | 0/0 |

For G1–G3, the one extra non-source path was the pre-existing `.git` worktree pointer; it is not an application file. Both other release trees had no extra files at the time of the original byte-level audit.

## GitHub updates

The three **immutable-intent deployment branches** above were newly created directly at the verified commit SHAs. They must not be advanced casually: each is a provenance record of a deployed or retained snapshot, **not** an instruction to redeploy it. The existing newer development branch `feature/v5-continuous-g4-g7-20261014` remained untouched. No `main`, G4 PR #39, G4–G7 PR #40, governance branch history, or other branch was merged, reset, or force-updated.

## Git metadata installed safely

- The Observation G1–G3 release already had a functional `.git` worktree pointer and resolved to the pinned commit. Its tracked source was clean.
- On the Observation research release and the Execution paper release, Git metadata was initialized **within the existing release directories** at their separately verified snapshot SHA using local Git object repositories. `git reset --mixed` rebuilt only Git index/metadata, without replacing application files. The GitHub origin remote was recorded, and a corresponding local `deploy/...` branch was created. Both showed empty `git status --porcelain` and clean staged/unstaged diffs after initialization.
- No running service, source code, Python virtual environment, SQLite/WAL database, account file, or original research evidence was restarted, rewritten, deleted, or altered by this reconciliation.

Useful read-only checks:

```bash
git -C /home/ubuntu/nbot_v5_integrated_20261014 rev-parse HEAD
git -C /home/ubuntu/nbot_v5_continuous_release_20261014 rev-parse HEAD
git -C /home/ubuntu/nbot_v5_continuous_release_20261014 status --porcelain
git -C /home/ubuntu/nbot_v5_continuous_release_20261014 branch --show-current
```

**Do not run `git pull`, `git reset --hard`, `git checkout`, or `git clean` against active release directories merely to match development HEAD.** Perform future changes through a verified, backed-up deployment process with rollback and new source hash audit.

## Exact running status at last read-only check

2026-10-14 13:24:33–13:24:40 UTC:

- Observation `nbot-v5-g1g2g3-observation.service`: **active**, PID 23196, source SHA `1e7c090d...`, service start 12:34:26 UTC, `NRestarts=1` following a **separate prior manual recovery**. Earlier original G1 lost its continuity evidence: market frame cap exit and source held events are not repaired by this Git reconciliation.
- Observation `nbot-v5-continuous-research.service`: **inactive**, PID 0. Code retained and verified at `dc4981c...`. This is *not* an operating integrated G4–G6 pipeline; G4 scientific outcome qualification remains unproven.
- Execution `nbot-v5-g7-locked.service`: **active**, PID 96888, source SHA `33a9c825...`, start 11:59:52 UTC, `NRestarts=0`; paper engine remains locked; no real-money order authority.

## Limitations and follow-up

All source files matched their respective pinned commits, but this audit did not revalidate third-party installed dependencies, systemd unit file parity, runtime environment variables, deployed state provenance, after-cost economic outcomes, or the scientific acceptance gates. The GitHub release branches are **historical snapshot pins**; the newer G4/G5/G6/G7 branch contains work not deployed at these pins. The correct next phase is a separate remediation review, not an automatic branch merge or unlock.
