# Webtoon Scene Anchor & ControlNet Strategy

When the user wants to create or use a scene background:

## What is a "scene anchor"?
A scene anchor is a high-quality reference image of a location plus extracted control maps (lineart, depth, canny). When generating panels set in that location, ControlNet uses the maps to keep architecture, perspective, and key landmarks consistent across many panels.

This is the difference between "a forest" and "**this** forest with the broken bridge over the river" — anchor + control maps preserve the latter.

## Step 1: Anchor scope
Decide what counts as one scene:
- **Same location** (one forest clearing, one room, one street corner) → one anchor
- **Same building, different rooms** → one anchor per room (lobby ≠ bedroom)
- **Outdoor with weather variants** → one anchor + variants for night/rain/etc

Don't bundle visually distinct locations into one anchor.

## Step 2: Anchor generation
Use `create_scene` to dispatch anchor generation. Provide:
- **Name**: short identifier (e.g., "moonlit forest clearing")
- **Description**: detailed visual prompt — the more architectural/spatial detail, the better the anchor

After generation, the anchor image + extracted control maps live in MinIO and are referenced by panel render jobs.

## Step 3: Using anchors in panel rendering
When a panel's setting matches an anchor:
1. Bind the anchor to the panel (the renderer attaches lineart/depth ControlNet automatically)
2. The render job uses the anchor's seed range as a starting point for visual continuity
3. Multiple panels in the same scene → all reference the same anchor → backgrounds stay consistent

## ControlNet weights — defaults work
- Lineart ControlNet: weight ~0.7 (preserves architecture)
- Depth ControlNet: weight ~0.5 (preserves spatial layout)
- Canny ControlNet: weight ~0.4 (edge preservation, lighter touch)

Don't tune weights unless QA reports specific drift; defaults handle 90% of cases.

## When to regenerate an anchor
- The first anchor is decent but the lighting / time-of-day is wrong → use `regenerate_asset_image` with `prompt_override` adjusting the lighting clause
- The architecture is wrong → regenerate; ControlNet maps re-extract automatically
- You want a "morning" and "night" version → create as two scenes (separate anchors), don't try to repurpose

## Tools
- `create_scene` — slow, dispatches anchor + control map generation
- `regenerate_asset_image` — re-rolls the anchor (with optional prompt override)
- `query_assets` (with `asset_type=scene`) — list existing scenes
- `analyze_quality` — check whether a panel's background drifted from the anchor

## When in doubt
If the user describes a setting that overlaps an existing scene (per `query_assets`), confirm whether they mean to reuse it or create a parallel variant.
