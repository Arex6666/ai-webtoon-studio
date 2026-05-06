# Webtoon Render Strategy

When the user wants to render panel images, this skill helps decide what to render, in what order, with what parameters.

## Decision: batch vs single

### Render batch (all panels in an episode)
- **Trigger**: user has approved the storyboard and assets, ready for "first cut"
- **Action**: call `render_panels` with `panel_ids` covering all panels of the current episode
- **Cost**: high time (each panel = 30s-3min); single Celery dispatch but many sub-jobs
- **UX**: tell the user the batch dispatched and they'll get notifications as panels complete

### Render single
- **Trigger**: panel-specific feedback ("redo panel 3"), QA fix application, last-minute tweak
- **Action**: call `render_panels` with one `panel_id`
- **Cost**: low; single job

### Don't render at all (yet)
If the user hasn't:
- approved character / scene assets, OR
- finalized the script / storyboard
…push back on rendering. Wasted renders are expensive. Suggest finishing earlier steps first.

## Render order in a batch
The renderer dispatches all panels in parallel by default — order doesn't affect outcome. But for COST AWARENESS:
- If the user wants a "preview" first, render only panels 1, last, and one in the middle (3 panels = quick read on whether the style/character is right)
- Then decide whether to render the rest

## Seed and denoise tuning

### Default seed strategy
- Each panel gets a deterministic seed derived from `(panel_id + version)` so reruns of the same panel are reproducible
- New panels: random seed
- Reroll: increment `version` to get a new seed but keep traceability

### Denoise strength
- **Defaults work** (0.5-0.7 range) for most cases
- **Lower (0.3)** for img2img where you want to preserve a previous render's composition
- **Higher (0.9)** for txt2img where the previous render is wrong and you want a fresh roll

### When to bump steps
- Default: 20-30 steps
- Bump to 40-50 if QA reports persistent low quality (slow)
- Don't bump above 50 — diminishing returns

## When QA fails in a batch
- Don't auto-rerender. Call `analyze_quality` + `suggest_fixes` first.
- Report the issue with specifics (which panel, which axis), let the user decide whether to fix or accept.

## Cost-aware ordering recommendations
1. **Cheapest first**: query_panels to see current state — don't re-render what's already good
2. **Fast preview**: render 3 sample panels first
3. **Full batch only after preview approved**

## Tools
- `render_panels` — slow, dispatches Celery render jobs
- `analyze_quality` — fast read-only check after render
- `query_panels` — list panel states (which are already rendered)

## When in doubt
If the user says "render everything" but hasn't reviewed the storyboard yet, ask once whether they're sure or want a preview first. If they confirm, go.
