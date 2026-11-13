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

EXPLANATION_PROMPT = """Rewrite the study material as a clear beginner-friendly explanation.

Education level: {education_level}
Subject/exam: {subject}

Material:
{raw_text}

Return STRICT JSON only (no markdown, no backticks):
{
  "content_blocks": [
    {"type":"heading","text":"...","level":2},
    {"type":"body","text":"..."},
    {"type":"list","items":["..."]},
    {"type":"tip","text":"..."},
    {"type":"recap","items":["..."]}
  ]
}
Use only these block types when appropriate: heading, body, list, numbered_list, tip, warning, definition, recap.
"""
