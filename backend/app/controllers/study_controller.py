"""Study controller (OOP)."""

import json
import logging
from datetime import datetime

from fastapi import HTTPException

from app.models.study import StudyAsset, StudyMaterial
from app.models.user import User
from app.repositories.study_repository import StudyAssetRepository, StudyMaterialRepository
from app.repositories.study_asset_queries import list_assets_for_material
from app.repositories.wallet_repository import WalletRepository
from app.services.ai_service import call_ai, parse_json_response
from app.services.study_unlock_service import StudyUnlockService

logger = logging.getLogger("uvicorn.error")

# AI prompts
MCQ_PROMPT = """Generate {count} multiple-choice questions from the following study material.

Material:
{content}

Output strict JSON only. No markdown. No backticks.
{{
  "questions": [
    {{
      "question": "Question text",
      "options": ["A", "B", "C", "D"],
      "correct_index": 0,
      "explanation": "Why this is correct"
    }}
  ]
}}

Rules: exactly {count} questions, 4 options each, correct_index 0-3, medium difficulty."""

FLASHCARD_PROMPT = """Generate {count} flashcards from the following study material.

Material:
{content}

Output strict JSON only. No markdown. No backticks.
{{
  "flashcards": [
    {{
      "front": "Question or term",
      "back": "Answer or definition"
    }}
  ]
}}

Rules: exactly {count} flashcards, concise front/back."""

ESSAY_PROMPT = """Generate {count} essay questions from the following study material.

Material:
{content}

Output strict JSON only. No markdown. No backticks.
{{
  "essays": [
    {{
      "prompt": "Essay question",
      "key_points": ["point1", "point2"],
      "sample_answer": "A model answer"
    }}
  ]
}}

Rules: exactly {count} essay questions, include key_points and sample_answer."""

ESSAY_REVIEW_PROMPT = """You are a friendly tutor reviewing a student's essay answer.

Topic: {topic}
Question: {question}
Student's answer: {essay}
Key points expected: {key_points}
Sample answer: {sample_answer}

Output strict JSON only. No markdown. No backticks.
{{
  "correct": true/false,
  "score": 0-100,
  "feedback": "Encouraging feedback",
  "suggestions": ["suggestion1", "suggestion2"]
}}

Rules: Be encouraging. Score based on coverage of key points. Provide actionable suggestions."""


class StudyController:
    """Orchestrates study use-cases."""

    def __init__(self, db):
        self.db = db
        self.materials = StudyMaterialRepository(db)
        self.assets = StudyAssetRepository(db)
        self.wallet_repo = WalletRepository(db)
        self.unlocks = StudyUnlockService(db)

    async def upload_material(self, current_user: User, title: str, content: str, exam_type: str | None, education_level: str | None) -> dict:
        material = StudyMaterial(
            user_id=current_user.id,
            title=title,
            exam_type=exam_type,
            education_level=education_level,
            raw_input=content,
            content=content,
        )
        await self.materials.create(material)
        return {
            "id": material.id,
            "title": material.title,
            "exam_type": material.exam_type,
            "education_level": material.education_level,
            "created_at": material.created_at.isoformat(),
        }

    async def get_material(self, current_user: User, material_id: int) -> dict:
        material = await self.materials.get_by_id(material_id, current_user.id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        parsed = None
        if material.parsed_structure:
            try:
                parsed = __import__("json").loads(material.parsed_structure)
            except Exception:
                parsed = None
        assets = await list_assets_for_material(self.db, material_id)
        asset_items = []
        for a in assets:
            unlocked = await self.wallet_repo.get_unlock(current_user.id, a.id) is not None
            item = {
                "id": a.id,
                "asset_type": a.asset_type,
                "topic": a.topic,
                "points_to_unlock": a.points_to_unlock,
                "unlocked": unlocked,
                "created_at": a.created_at.isoformat(),
            }
            if unlocked and a.content_json:
                try:
                    item["content"] = __import__("json").loads(a.content_json)
                except Exception:
                    item["content"] = None
            asset_items.append(item)
        return {
            "id": material.id,
            "title": material.title,
            "exam_type": material.exam_type,
            "education_level": material.education_level,
            "content": material.content,
            "parsed_structure": parsed,
            "assets": asset_items,
            "created_at": material.created_at.isoformat(),
        }

    async def list_materials(self, current_user: User) -> list[dict]:
        materials = await self.materials.list_for_user(current_user.id)
        result = []
        for m in materials:
            assets = await self.assets.list_for_material(m.id)
            asset_types = list(set(a.asset_type for a in assets))
            result.append({
                "id": m.id,
                "title": m.title,
                "exam_type": m.exam_type,
                "asset_types": asset_types,
                "created_at": m.created_at.isoformat(),
            })
        return result

    async def generate_asset(self, current_user: User, material_id: int, asset_type: str, count: int, topic: str | None, difficulty: str) -> dict:
        material = await self.materials.get_by_id(material_id, current_user.id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        content = material.content or material.raw_input
        if not content:
            raise HTTPException(status_code=400, detail="Material has no content")

        if asset_type == "mcq":
            prompt = MCQ_PROMPT.format(content=content, count=count)
        elif asset_type == "flashcard":
            prompt = FLASHCARD_PROMPT.format(content=content, count=count)
        elif asset_type == "essay":
            prompt = ESSAY_PROMPT.format(content=content, count=count)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown asset type: {asset_type}")

        ai_response = await call_ai(prompt)
        try:
            parsed = await parse_json_response(ai_response)
        except ValueError:
            raise HTTPException(status_code=502, detail="AI returned invalid format. Try again.")

        asset = StudyAsset(
            material_id=material_id,
            asset_type=asset_type,
            content_json=__import__("json").dumps(parsed),
            points_to_unlock=50,
        )
        await self.assets.create(asset)

        return {
            "material_id": material_id,
            "asset_id": asset.id,
            "asset_type": asset_type,
            "points_to_unlock": asset.points_to_unlock,
            "unlocked": False,
            "message": "Asset generated. Unlock with SP to access content.",
        }

    async def unlock_asset(self, current_user: User, asset_id: int) -> dict:
        return await self.unlocks.unlock_asset(current_user.id, asset_id)

    async def submit_essay(self, current_user: User, material_id: int, topic: str | None, essay: str) -> dict:
        material = await self.materials.get_by_id(material_id, current_user.id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        content = material.content or material.raw_input
        question = topic or "General essay question"
        key_points = "Based on the material content"
        sample_answer = "A comprehensive answer covering the key concepts"

        prompt = ESSAY_REVIEW_PROMPT.format(
            topic=topic or "General",
            question=question,
            essay=essay,
            key_points=key_points,
            sample_answer=sample_answer,
        )

        ai_response = await call_ai(prompt)
        try:
            result = await parse_json_response(ai_response)
        except ValueError:
            raise HTTPException(status_code=502, detail="AI returned invalid format. Try again.")

        return {
            "correct": result.get("correct", False),
            "score": result.get("score", 0),
            "feedback": result.get("feedback", "Keep trying!"),
            "suggestions": result.get("suggestions", []),
        }
