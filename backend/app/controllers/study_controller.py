"""Study controller (OOP)."""

import json
import logging

from fastapi import HTTPException

from app.models.study import StudyAsset, StudyMaterial
from app.models.user import User
from app.repositories.study_asset_queries import list_assets_for_material
from app.repositories.study_repository import StudyAssetRepository, StudyMaterialRepository
from app.repositories.wallet_repository import WalletRepository
from app.services.ai_service import call_ai, parse_json_response
from app.services.study_unlock_service import StudyUnlockService
from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

# AI prompts
MCQ_PROMPT = """Generate {count} multiple-choice questions from the following study material.

Material:
{content}

{focus_block}
{difficulty_block}

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

Rules: exactly {count} questions, 4 options each, correct_index 0-3."""

FLASHCARD_PROMPT = """Generate {count} flashcards from the following study material.

Material:
{content}

{focus_block}
{difficulty_block}

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

{focus_block}
{difficulty_block}

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


def _focus_block(topic: str | None) -> str:
    return f"Focus topic: {topic}" if topic else ""


def _difficulty_block(difficulty: str | None, asset_type: str) -> str:
    level = (difficulty or "medium").lower()
    if asset_type == "mcq":
        return f"Difficulty: {level}. Adjust question complexity accordingly."
    if asset_type == "flashcard":
        return f"Difficulty: {level}. Use simpler prompts/terms for easy, deeper recall for hard."
    return f"Difficulty: {level}. Adjust depth and expectations accordingly."


class StudyController:
    """Orchestrates study use-cases."""

    def __init__(self, db):
        self.db = db
        self.materials = StudyMaterialRepository(db)
        self.assets = StudyAssetRepository(db)
        self.wallet_repo = WalletRepository(db)
        self.unlocks = StudyUnlockService(db)

    async def _get_owned_material(self, current_user: User, material_id: int) -> StudyMaterial:
        material = await self.materials.get_by_id(material_id, current_user.id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        return material

    async def _get_owned_asset(self, current_user: User, asset_id: int) -> tuple[StudyAsset, StudyMaterial]:
        asset = await self.assets.get_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        material = await self.materials.get_by_id(asset.material_id, current_user.id)
        if not material:
            raise HTTPException(status_code=404, detail="Asset not found")
        return asset, material

    async def upload_material(self, current_user: User, title: str, content: str, exam_type: str | None, education_level: str | None) -> dict:
        logger.info("study.material.upload start user=%s title=%r exam_type=%s education_level=%s content_len=%s", current_user.id, title, exam_type, education_level, len(content or ""))
        material = StudyMaterial(
            user_id=current_user.id,
            title=title,
            exam_type=exam_type,
            education_level=education_level,
            raw_input=content,
            content=content,
        )
        await self.materials.create(material)
        logger.info("study.material.upload ok user=%s material_id=%s", current_user.id, material.id)
        return {
            "id": material.id,
            "title": material.title,
            "exam_type": material.exam_type,
            "asset_types": [],
            "created_at": material.created_at.isoformat(),
        }

    async def upload_material_file(
        self,
        current_user: User,
        title: str | None,
        exam_type: str | None,
        education_level: str | None,
        data: bytes,
        filename: str,
        mime: str,
        extracted_text: str,
        page_count: int,
    ) -> dict:
        use_title = (title or "").strip() or (filename.rsplit(".", 1)[0] if "." in filename else filename) or "Uploaded material"
        logger.info("study.material.upload_file start user=%s filename=%r mime=%s bytes=%s pages=%s", current_user.id, filename, mime, len(data), page_count)
        material = StudyMaterial(
            user_id=current_user.id,
            title=use_title[:500],
            exam_type=exam_type,
            education_level=education_level,
            raw_input=extracted_text,
            content=extracted_text,
            original_file_data=data,
            file_mime_type=mime,
            page_count=page_count or 0,
        )
        await self.materials.create(material)
        logger.info("study.material.upload_file ok user=%s material_id=%s", current_user.id, material.id)
        return {
            "id": material.id,
            "title": material.title,
            "exam_type": material.exam_type,
            "asset_types": [],
            "created_at": material.created_at.isoformat(),
        }

    async def get_material(self, current_user: User, material_id: int) -> dict:
        logger.info("study.material.get user=%s material_id=%s", current_user.id, material_id)
        material = await self._get_owned_material(current_user, material_id)
        parsed = None
        if material.parsed_structure:
            try:
                parsed = json.loads(material.parsed_structure)
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
                    item["content"] = json.loads(a.content_json)
                except Exception:
                    item["content"] = None
            asset_items.append(item)
        logger.info("study.material.get ok user=%s material_id=%s assets=%s", current_user.id, material_id, len(asset_items))
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
        logger.info("study.material.list user=%s", current_user.id)
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
        logger.info("study.material.list result user=%s count=%s", current_user.id, len(result))
        return result

    async def update_material(
        self, current_user: User, material_id: int, title: str | None, content: str | None, exam_type: str | None, education_level: str | None
    ) -> dict:
        material = await self._get_owned_material(current_user, material_id)
        if title is not None:
            material.title = title
        if exam_type is not None:
            material.exam_type = exam_type
        if education_level is not None:
            material.education_level = education_level
        if content is not None:
            material.content = content
            material.raw_input = content
        await self.materials.update(material)
        return {
            "id": material.id,
            "title": material.title,
            "exam_type": material.exam_type,
            "asset_types": list(set(a.asset_type for a in await self.assets.list_for_material(material.id))),
            "created_at": material.created_at.isoformat(),
        }

    async def delete_material(self, current_user: User, material_id: int) -> None:
        material = await self._get_owned_material(current_user, material_id)
        await self.wallet_repo.delete_unlocks_for_material(material_id)
        assets = await self.assets.list_for_material(material_id)
        for a in assets:
            await self.db.delete(a)
        await self.db.delete(material)
        await self.db.commit()
        logger.info("study.material.delete ok user=%s material_id=%s assets_deleted=%s", current_user.id, material_id, len(assets))

    async def generate_asset(self, current_user: User, material_id: int, asset_type: str, count: int, topic: str | None, difficulty: str) -> dict:
        logger.info("study.asset.generate start user=%s material_id=%s asset_type=%s count=%s topic=%s difficulty=%s", current_user.id, material_id, asset_type, count, topic, difficulty)
        material = await self._get_owned_material(current_user, material_id)

        content = material.content or material.raw_input
        if not content:
            raise HTTPException(status_code=400, detail="Material has no content")

        focus = _focus_block(topic)
        diff = _difficulty_block(difficulty, asset_type)
        if asset_type == "mcq":
            prompt = MCQ_PROMPT.format(content=content, count=count, focus_block=focus, difficulty_block=diff)
        elif asset_type == "flashcard":
            prompt = FLASHCARD_PROMPT.format(content=content, count=count, focus_block=focus, difficulty_block=diff)
        elif asset_type == "essay":
            prompt = ESSAY_PROMPT.format(content=content, count=count, focus_block=focus, difficulty_block=diff)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown asset type: {asset_type}")

        ai_response = await call_ai(prompt)
        try:
            parsed = await parse_json_response(ai_response)
        except ValueError:
            logger.error("study.asset.generate AI invalid JSON user=%s material_id=%s asset_type=%s", current_user.id, material_id, asset_type)
            raise HTTPException(status_code=502, detail="AI returned invalid format. Try again.")

        asset = StudyAsset(
            material_id=material_id,
            asset_type=asset_type,
            topic=topic,
            content_json=json.dumps(parsed),
            points_to_unlock=int(getattr(settings, "study_unlock_default_points", 50) or 50),
        )
        await self.assets.create(asset)
        logger.info("study.asset.generate ok user=%s material_id=%s asset_id=%s asset_type=%s points_to_unlock=%s", current_user.id, material_id, asset.id, asset_type, asset.points_to_unlock)

        return {
            "material_id": material_id,
            "asset_id": asset.id,
            "asset_type": asset_type,
            "topic": asset.topic,
            "points_to_unlock": asset.points_to_unlock,
            "unlocked": False,
            "message": "Asset generated. Unlock with SP to access content.",
        }

    async def update_asset(self, current_user: User, asset_id: int, topic: str | None) -> dict:
        asset, _ = await self._get_owned_asset(current_user, asset_id)
        if topic is not None:
            asset.topic = topic
        await self.assets.update(asset)
        unlocked = await self.wallet_repo.get_unlock(current_user.id, asset.id) is not None
        return {
            "id": asset.id,
            "material_id": asset.material_id,
            "asset_type": asset.asset_type,
            "topic": asset.topic,
            "points_to_unlock": asset.points_to_unlock,
            "unlocked": unlocked,
            "created_at": asset.created_at.isoformat(),
        }

    async def delete_asset(self, current_user: User, asset_id: int) -> None:
        asset, _ = await self._get_owned_asset(current_user, asset_id)
        await self.wallet_repo.delete_unlocks_for_asset(asset_id)
        await self.db.delete(asset)
        await self.db.commit()
        logger.info("study.asset.delete ok user=%s asset_id=%s", current_user.id, asset_id)

    async def unlock_asset(self, current_user: User, asset_id: int) -> dict:
        logger.info("study.asset.unlock start user=%s asset_id=%s", current_user.id, asset_id)
        res = await self.unlocks.unlock_asset(current_user.id, asset_id)
        logger.info("study.asset.unlock result user=%s asset_id=%s applied=%s", current_user.id, asset_id, res.get("applied") if isinstance(res, dict) else None)
        return res

    async def submit_essay(self, current_user: User, material_id: int, topic: str | None, essay: str, asset_id: int | None = None, question_index: int = 0) -> dict:
        logger.info("study.essay.submit start user=%s material_id=%s asset_id=%s topic=%s essay_len=%s", current_user.id, material_id, asset_id, topic, len(essay or ""))
        material = await self._get_owned_material(current_user, material_id)

        question = topic or "General essay question"
        key_points = "Based on the material content"
        sample_answer = "A comprehensive answer covering the key concepts"
        used_topic = topic or "General"

        if asset_id is not None:
            asset, asset_material = await self._get_owned_asset(current_user, asset_id)
            if asset.material_id != material_id:
                raise HTTPException(status_code=400, detail="asset_id does not belong to the provided material_id")
            if asset.asset_type != "essay":
                raise HTTPException(status_code=400, detail="asset_id must reference an essay asset")
            try:
                data = json.loads(asset.content_json) if asset.content_json else {}
            except Exception:
                data = {}
            essays = data.get("essays") if isinstance(data, dict) else None
            if not isinstance(essays, list) or not essays:
                raise HTTPException(status_code=400, detail="Essay asset has no questions")
            if question_index < 0 or question_index >= len(essays):
                raise HTTPException(status_code=400, detail=f"question_index out of range (0..{len(essays)-1})")
            item = essays[question_index] if isinstance(essays[question_index], dict) else {}
            question = item.get("prompt") or question
            kp = item.get("key_points")
            if isinstance(kp, list) and kp:
                key_points = "; ".join(str(x) for x in kp)
            elif isinstance(kp, str) and kp.strip():
                key_points = kp
            sample_answer = item.get("sample_answer") or sample_answer
            used_topic = asset.topic or topic or "General"

        prompt = ESSAY_REVIEW_PROMPT.format(
            topic=used_topic,
            question=question,
            essay=essay,
            key_points=key_points,
            sample_answer=sample_answer,
        )

        ai_response = await call_ai(prompt)
        try:
            result = await parse_json_response(ai_response)
        except ValueError:
            logger.error("study.essay.submit AI invalid JSON user=%s material_id=%s", current_user.id, material_id)
            raise HTTPException(status_code=502, detail="AI returned invalid format. Try again.")

        logger.info("study.essay.submit ok user=%s material_id=%s correct=%s score=%s", current_user.id, material_id, result.get("correct"), result.get("score"))
        return {
            "correct": result.get("correct", False),
            "score": result.get("score", 0),
            "feedback": result.get("feedback", "Keep trying!"),
            "suggestions": result.get("suggestions", []),
        }
