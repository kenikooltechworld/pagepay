"""Prompts for study material parsing/generation (lightweight)."""

SOW_PARSER_PROMPT = """You are an expert tutor. Parse the following study material into a structured JSON outline.

Material:
{raw_text}

Return STRICT JSON only (no markdown, no backticks) with this shape:
{
  "title": "Short descriptive title",
  "summary": "2-4 sentence summary",
  "topics": [
    {
      "name": "Topic name",
      "subtopics": ["subtopic 1", "subtopic 2"],
      "key_points": ["point 1", "point 2"]
    }
  ]
}
"""

EXPLANATION_PROMPT = """You are an expert curriculum designer turning a student's study material into a clear teaching layer.

Rewrite the source in plain, student-friendly language appropriate for the learner. Preserve the source's important structure: headings, lists, worked calculations, code, quotations, formulas, definitions, tables, and diagrams must remain distinct typed blocks instead of being flattened into prose. Do not invent facts, examples, figures, or citations.

Education level: {education_level}
Subject/exam: {subject}

Source material (chunked with stable IDs such as [c1]; cite those IDs in source_refs):
{raw_text}

Return strict JSON only: no markdown, backticks, or surrounding text.
{{
  "content_blocks": [
    {{"type": "heading", "text": "Section title", "level": 1, "source_refs": ["c1"]}},
    {{"type": "body", "text": "A clear paragraph explaining the source.", "source_refs": ["c1"]}},
    {{"type": "list", "items": ["First point", "Second point"], "source_refs": ["c1"]}},
    {{"type": "numbered_list", "items": ["First step", "Second step"], "source_refs": ["c1"]}},
    {{"type": "tip", "text": "A useful study hint."}},
    {{"type": "warning", "text": "A common mistake to avoid."}},
    {{"type": "calculation", "text": "A worked calculation.", "steps": ["Step 1", "Step 2"]}},
    {{"type": "code", "text": "Source code with indentation intact", "language": "python"}},
    {{"type": "quote", "text": "The quoted text.", "attribution": "Source"}},
    {{"type": "formula", "text": "E = mc^2", "description": "What the formula means."}},
    {{"type": "statement", "text": "A key fact or theorem to remember."}},
    {{"type": "definition", "term": "Term", "text": "Its definition."}},
    {{"type": "table", "headers": ["Column 1", "Column 2"], "rows": [["a", "b"]]}},
    {{"type": "figure", "figure_index": 1, "page": 1, "caption": "Caption", "text": "What the source diagram shows."}},
    {{"type": "recap", "items": ["The most important point to remember."]}}
  ]
}}

Rules:
- Use only these block types: heading, body, list, numbered_list, tip, warning, calculation, code, quote, formula, statement, definition, table, figure, recap.
- Heading levels must be 1, 2, or 3. Lists and recaps require an items array of strings.
- Definitions require term and text. Tables require headers and rows containing strings.
- Figures require a 1-based figure_index; include page when known. Only describe figures present in the source.
- Formulas use LaTeX in text; preserve code indentation and calculation steps.
- Add source_refs containing only IDs present in the input to blocks making factual claims.
- Keep all meaningful source content; use enough blocks to preserve its organization, not one summary paragraph.
- End with a recap block containing the key takeaways."""


LESSON_GENERATION_PROMPT = """You are an expert teacher creating an interactive, chunked lesson from a student's study material.

Teach in short cycles (do NOT dump everything then explain at the end). For each segment: set a micro-goal, present a small source chunk, explain immediately in plain language, give an example/analogy, model thinking with step-by-step worked demonstration when applicable, check understanding with a question, provide guided practice then independent practice, then bridge and recap before the next segment.

Learner level: {education_level}
Subject/exam: {subject}

Parsed outline (may be partial):
{parsed}

Source material (use this as ground truth, do not invent facts):
{raw_text}

Return STRICT JSON only (no markdown, no backticks) with this exact shape:
{{
  "intro": {{
    "title": "Lesson title",
    "goals": ["What the learner will be able to do"],
    "why_it_matters": "Why this matters to the learner",
    "prior_knowledge": ["What the learner should already know or recall"],
    "overview": "Short signposted overview of the lesson parts"
  }},
  "segments": [
    {{
      "index": 0,
      "title": "Segment title",
      "micro_goal": "What this chunk achieves",
      "source_chunk": "Small excerpt/paraphrase anchor from the source for this chunk",
      "key_terms": [{{"term": "Term", "definition": "Plain-language definition (define before using)"}}],
      "explanation": "Plain-language explanation of this chunk (restate ideas accessibly)",
      "example": "A concrete example or analogy",
      "modeled_thinking": "Think-aloud: how to read/approach/solve this",
      "worked_steps": ["Step 1 ...", "Step 2 ..."],
      "check": {{
        "question": "Question to check understanding before moving on",
        "type": "short_answer",
        "expected_answer": "Model/expected answer",
        "key_points": ["Point that must appear in a good answer"],
        "misconceptions": [{{"pattern": "common wrong idea keyword/phrase", "feedback": "Correction/explanation"}}]
      }},
      "guided_practice": {{
        "prompt": "Do this together (scaffolded)",
        "hint": "Helpful hint",
        "solution": "Worked solution/answer"
      }},
      "independent_practice": {{
        "prompt": "Try this independently (relevant to level/exam)",
        "rubric": ["What a correct response includes"]
      }},
      "bridge_recap": "1-2 point recap of this chunk and transition to the next"
    }}
  ],
  "outro": {{
    "summary": ["Key takeaways"],
    "common_pitfalls": ["Common mistakes to avoid"],
    "next_steps": "What to study or practice next / assessment link"
  }}
}}

Rules:
- Create 3 to 6 ordered segments that together cover the important source content (chunked, not one block).
- Every segment must include all fields above (use empty arrays/strings when a field truly does not apply, but prefer meaningful content).
- Keep source_chunk small (a focused part, not the whole chapter). Explain immediately after it.
- Define key_terms before relying on them in explanation. Signpost transitions in bridge_recap.
- Check understanding, guided practice, and independent practice must be specific to that segment and appropriate for the learner level/exam.
- Preserve important structure (steps, formulas, definitions) inside explanation/worked_steps.
"""

LESSON_CHECK_PROMPT = """You are a supportive teacher giving feedback on a learner's response during an interactive lesson.

Learner level: {education_level}
Subject/exam: {subject}

Segment micro-goal: {micro_goal}
Question/prompt ({item_type}): {question}
Expected answer/model: {expected_answer}
Key points/rubric: {key_points}
Known misconceptions: {misconceptions}

Learner answer:
{answer}

Return STRICT JSON only (no markdown, no backticks):
{{
  "correct": true,
  "feedback": "Clear, specific feedback explaining why correct/incorrect and addressing misconceptions if present",
  "misconception": "Name/describe the misconception detected, or null",
  "can_continue": true,
  "model_answer": "A good/model answer to learn from"
}}

Rules:
- Be encouraging but accurate. Correct misconceptions explicitly with explanation.
- For short_answer/check: can_continue true if the core key points are present (minor wording ok).
- For guided/independent practice: judge against rubric/key points at the stated level; can_continue true when substantially correct, else false with guidance.
- If the answer is blank or irrelevant, correct is false, can_continue false, and give a helpful hint in feedback.
"""
