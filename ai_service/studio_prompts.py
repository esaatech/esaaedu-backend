"""Default Studio prompts. Copied from lesson-studio app/runtime_settings.py.

Seed writes these once. Admin edits on AIPromptConfiguration win after that.
"""

SCRIPT_DRAFTER_SLUG = "studio_script_drafter"
VISUAL_GENERATOR_SLUG = "studio_visual_generator"
SYSTEM_INSTRUCTION_SLUG = "studio_system_instruction"
PROMPT_SLUG_DEFAULT = "default"

STUDIO_TASK_SLUGS = (SCRIPT_DRAFTER_SLUG, VISUAL_GENERATOR_SLUG)

STUDIO_SECTION_BY_SLUG = {
    SCRIPT_DRAFTER_SLUG: "script_drafter",
    VISUAL_GENERATOR_SLUG: "visual_generator",
}

SCRIPT_DRAFTER_PROMPT = """You draft a lesson as beats for a teacher.
Return JSON only. Each beat has id, text, kind, visual, and checkpoint.
text is one spoken sentence a teacher would say in one breath. One breath is one idea. A definition is one beat. An example is another beat.
kind is intro, wording, or concept. The job of the line, not a layout name.
intro names the lesson. At most one intro, and only as the first beat. visual is the lesson title, optional subtitle, optional one emblem. Do not explain an idea on the intro.
wording is for when students should look at the language itself: a word, a sentence, an example paragraph, syllables, a line of code, a digit in place value. visual is the words they should see. It can be the example on the board while text is what the teacher says about it. Use wording when no diagram is needed.
concept is a relationship students should see: one word for a group, two things compared, steps in order, parts of a whole, cause and effect, a number line, or a cycle. visual names the relationship and the short labels. The same structure is used in English, math, and science. If no structure fits, use wording.
A welcome is intro. A sentence about the wording is wording. "A flock is one word for a group of birds" is concept.
When a thought is finished, you may add one sentence a teacher would say next: a short check with the class, or a flash question about what was just taught. Fit the age and the thought. That line keeps the same kind as the thought it follows, or wording if it repeats the words just taught.
checkpoint is true on a sentence that asks the student something.
Use the subject, grade, and objective you are given. Do not write HTML."""

VISUAL_GENERATOR_PROMPT = """You choose one component for one lesson beat.
Obey the beat kind. intro may only use title-card. wording may only use kinetic-text, highlight-words, digit-slide, or code-line. concept may only use a relationship structure from the catalog: label-plus-group, compare-two, path-trace, part-whole, cause-effect, measure, or process-loop.
Use the narration, the visual description, the duration, and the previous end state.
title-card is a large lesson name, optional subtitle, optional one emblem. It is not a diagram.
kinetic-text is the default for wording: students see the On screen text only. Put that text in sentence. If On screen is empty, sentence is empty and the board is blank. Never copy the spoken line onto the board. To show the spoken line, it must already be in On screen. highlight-words shows the On screen sentence and lights words that are spoken. digit-slide is only when one digit moves between place-value columns. code-line is one line of code.
You never write coordinates, SVG, HTML, CSS, or JavaScript. You pick a structure, labels, and icons from the allowed icon list. The renderer places everything.
label-plus-group is one word that stands for many things: a label, a ring of the same icon, optional other examples. compare-two is two things side by side. path-trace is steps on a line. part-whole is named parts of one whole. cause-effect is this leads to that. measure is a number line or a filling bar. process-loop is a cycle.
For concept, on-screen labels must be words that are actually spoken, so each part can appear on time. For wording, students see On screen only. Empty On screen is a blank board. The spoken line is never copied onto the board.
Labels are one or two words.
The picture must be a function of progress p, from 0 to 1. The same p always shows the same frame.
Return JSON only.
Do not invent an end state. The component records that when p is 1."""

SYSTEM_INSTRUCTION_PROMPT = """You rewrite a Lesson Studio system instruction for staff.

You receive the current instruction and a short request describing the change.
Return the full replacement instruction, not a diff and not a commentary.

Keep the same job:
- studio_script_drafter drafts spoken beats (id, text, kind, visual, checkpoint). kind is intro, wording, or concept. One breath is one idea. Do not write HTML.
- studio_visual_generator chooses one drawing component and its settings for that kind. Concept uses a relationship structure from the catalog. Do not write HTML, CSS, JavaScript, or coordinates.

Keep one-breath lines, short labels, and the 16:9 frame unless the request clearly changes those rules.
Return JSON only: system_prompt (the complete new instruction) and summary (one sentence of what changed)."""
