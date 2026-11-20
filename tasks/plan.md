# Implementation Plan: <project> V1

Source spec: [`SPEC.md`](../SPEC.md)
**Tasks are tracked as GitHub issues** in <owner/repo>. The index below is the ordered map; the issues are the source of truth.

## Overview
<N>-hour build. <one-paragraph shape of the system>.

## Architecture Decisions
- **Contract first.** Build modules in parallel against fixtures; swap real data in later.
- **Single owner per file.** Each issue lists "Files owned by this issue".
- **Thin vertical slice before breadth.** One real path end-to-end and deployed by the first checkpoint.
- **Riskiest work first.**

## Labels & Milestones
- **Priority:** `priority:P0-critical` · `P0` · `P1` · `P2`
- **Area:** `area:<x>` per module · **Size:** `size:XS/S/M` · `risk`
- **Milestones** = phases. **Checkpoint issues** are phase gates blocked by every issue in their phase.

## Roles
| Role | Issues |
|---|---|
| | |

## Issue Index
### Phase 0: Foundation
| Issue | Task | Prio | Blocked by |
|---|---|---|---|
| #1 | Spec, plan, contributing guide | P0-crit | — |
