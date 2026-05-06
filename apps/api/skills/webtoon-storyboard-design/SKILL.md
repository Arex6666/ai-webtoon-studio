# Webtoon Storyboard Design

When the user asks for a storyboard, panel breakdown, or "分镜":

## Step 1: Understand the story
- Read the user's narrative carefully. Identify: protagonist(s), conflict, setting, key emotional beats.
- If the story is vague (<2 sentences), ask one clarifying question before proceeding.
- Note the genre tone (action, romance, horror, slice-of-life) — it shapes pacing decisions.

## Step 2: Pick panel count
- Default 4-6 panels for a short scene; 8-12 for an episode segment.
- If user specifies a number, use it (clamp 1-20).
- Beat count drives panel count more than time elapsed: each emotional shift = 1+ panel.

## Step 3: Draft each panel as a structured beat
For each panel produce:
- **Camera**: shot type (wide / medium / close-up / over-the-shoulder / POV / extreme close-up) + angle (eye-level / low / high / Dutch / bird's-eye)
- **Subject**: who/what is in frame, their pose, their expression
- **Setting**: brief description of the visible portion of the scene
- **Action**: what is happening — verb-driven, present tense
- **Dialogue/SFX**: speech bubbles or sound effects, with speaker names
- **Pacing note**: time elapsed since previous panel (instant / seconds / minutes / longer / flashback)

## Step 4: Validate the breakdown
Ask yourself:
- Does the camera vary across panels? Avoid 4 medium shots in a row.
- Are emotional peaks at panels 3-4 of a 5-panel sequence?
- Is there a hook at panel 1 (visual or question that pulls the reader in)?
- Does the final panel land cleanly (cliffhanger, resolution, or transition)?

## Step 5: Use tools to commit
- Call `generate_script` with the structured beats once user approves the outline
- Call `refine_script` if iterating on a previous version
- Call `analyze_script` first if the user provided a finished script and you want a structured view
- Do NOT call `render_panels` until user explicitly says they want images

## Webtoon-specific guidance
- **Vertical scroll** is the dominant format; allow occasional full-width "splash" panels for impact
- **Bubble placement**: keep dialogue bubbles in the upper third of each panel for natural reading flow
- **Onomatopoeia (SFX)**: integrate as visual elements, not just labels — they carry mood
- **Transition panels**: empty / sparse panels between scenes give breathing room

## When in doubt
If the user's request is ambiguous about scope (one scene vs whole episode), ask before producing 12 panels of speculative work.
