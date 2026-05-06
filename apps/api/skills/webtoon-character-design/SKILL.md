# Webtoon Character Design

When the user wants to create or refine a character:

## Step 1: Gather the character sheet basics
A character needs:
- **Name** (and aliases / honorifics if relevant)
- **Role** in the story (protagonist / antagonist / support / cameo)
- **Visual identity**: age, build, distinctive features (scars, accessories, signature pose)
- **Appearance specifics**: hair style + color, eye shape + color, skin tone, clothing baseline
- **Voice / personality**: 2-3 traits that affect dialogue and posture

If user gives only name + vague role, ask one targeted question (e.g. "What does she look like in your head?") before invoking `create_character`.

## Step 2: Plan FaceID reference selection
For consistency across panels, the character needs a FaceID embedding. The reference image used to extract that embedding determines all future portraits.

Prioritize reference quality:
- **Clear front-facing face**, neutral expression, even lighting
- **No occlusions** (hair across face, hand near jaw, glasses with heavy reflection)
- **Distinct features visible** (eye shape, brow shape, lip line, jawline)

If the user hasn't provided a reference, the `create_character` tool will dispatch portrait generation; the result becomes the canonical reference. Tell the user this and that they can regenerate via `regenerate_asset_image` if the first portrait isn't right.

## Step 3: Outfit variants
A character usually wears multiple outfits across scenes. Track them as variants:
- **Default**: everyday wear
- **Story-key**: outfits tied to specific scenes (battle armor, formal dress, transformation form)
- **Casual / formal / pajama** — common axes

Outfits are NOT separate characters — they're variants on the same FaceID.

## Step 4: Use tools
- `create_character` — creates the Asset row, dispatches portrait generation. Provide name, description, appearance.
- `regenerate_asset_image` — re-rolls the portrait if the first attempt doesn't match the user's vision (use `prompt_override` for targeted tweaks like "make the hair shorter").
- `query_assets` (with `asset_type=character`) — list existing characters before creating to avoid duplicates.
- `update_panel_*` — to wire a character into a specific panel's spec.

## Consistency rules
- **Don't change canonical appearance mid-story** without flagging it (transformations, time skips, reveals are exceptions).
- **Same FaceID → same character** across all panels in an episode.
- **Outfit drift is OK**, identity drift is not.

## When in doubt
If the user names a character that already exists in the project (per `query_assets`), confirm whether they mean to update it or create a similar new one.
