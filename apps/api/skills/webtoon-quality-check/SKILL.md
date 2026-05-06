# Webtoon Quality Check & Fix Decision Tree

After a panel renders, automated QA can score it on three axes. This skill guides interpretation and remediation.

## QA dimensions
- **FaceID drift** — does the rendered character match its canonical reference? (drift > threshold = the LLM-rendered face wandered)
- **Style consistency** — does the panel's overall art style match the project's StyleProfile?
- **Composition score** — is the framing, contrast, and subject placement coherent?

Each scored 0.0–1.0. Default pass threshold: 0.7. Below 0.7 → QA fails → suggest a fix.

## When to invoke analyze_quality
- After every render that the user wants to "approve" or "lock"
- Before commit_to_studio
- When the user complains visually about a panel
- NOT after every render in a batch — wait for the user to flag something

Tool: `analyze_quality` (read-only, fast).

## Reading the result
Returns `{score, passed, issues}`:
- `passed=true, score≥0.7` — Move on. Don't waste tokens explaining further.
- `passed=true, score 0.7-0.85` — Mention any specific issues but don't push fixes unprompted.
- `passed=false, score<0.7` — Explain the dominant issue from `issues[]`, then call `suggest_fixes`.

## FixPlan decision tree
`suggest_fixes` returns a structured FixPlan. Common strategies and when to apply:

### Strategy: Re-seed
- **Trigger**: low composition score, or "feels random" complaints
- **Action**: re-run render with a new seed (low cost)
- **Don't apply if**: FaceID drift is the actual problem (re-seed won't help, will re-roll the face badly)

### Strategy: Boost FaceID weight
- **Trigger**: FaceID drift > 0.3 (face wandered)
- **Action**: re-render with `faceid_weight` increased from 0.6 → 0.8
- **Cost**: slight loss of natural pose variation; acceptable for character-key panels
- **Don't apply if**: the character's REFERENCE image is itself bad — fix the reference first via `regenerate_asset_image`

### Strategy: Inpaint
- **Trigger**: most of the panel is good but one region is broken (extra finger, melted face)
- **Action**: render an inpaint mask covering the bad region
- **Cost**: slow; same as a fresh render
- **Don't apply if**: >40% of the panel needs fixing — full re-render is cheaper to reason about

### Strategy: Style transfer
- **Trigger**: style consistency score < 0.6
- **Action**: re-render with stronger StyleProfile weight or different LoRA
- **Don't apply if**: it's the FIRST panel of a project — the style might just need to settle

### Strategy: Accept
- **Trigger**: score 0.65-0.7 borderline, with no clear issue identified
- **Action**: tell the user the score, ask if they're satisfied, accept their call

## When in doubt
If the FixPlan suggests something the user hasn't asked for (e.g., regenerate a character reference), surface it as a question, don't auto-apply. Image regeneration costs time and tokens.
