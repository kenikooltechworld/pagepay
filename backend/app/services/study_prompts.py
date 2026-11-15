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
