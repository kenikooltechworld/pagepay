"""Study controller (OOP)."""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime

from fastapi import HTTPException

from app.models.study import SowUploadJob, StudyAsset, StudyLessonProgress, StudyMaterial
from app.models.user import User
from app.repositories.study_asset_queries import list_assets_for_material
from app.repositories.study_repository import SowUploadJobRepository, StudyAssetRepository, StudyLessonProgressRepository, StudyMaterialRepository
from app.repositories.wallet_repository import WalletRepository
from app.services.ai_service import call_ai, call_ai_vision, parse_json_response
from app.services.study_unlock_service import StudyUnlockService
from app.core.config import settings
from app.services.study_prompts import EXPLANATION_PROMPT, LESSON_CHECK_PROMPT, LESSON_GENERATION_PROMPT, SOW_PARSER_PROMPT

logger = logging.getLogger("uvicorn.error")

_EXPLANATION_BLOCK_FIELDS = {
    "heading": ({"text"}, {"level"}),
    "body": ({"text"}, set()),
    "list": ({"items"}, set()),
    "numbered_list": ({"items"}, set()),
    "tip": ({"text"}, {"items", "label"}),
    "warning": ({"text"}, {"items", "label"}),
    "calculation": (set(), {"text", "steps", "description", "label"}),
    "code": ({"text"}, {"language", "label"}),
    "quote": ({"text"}, {"attribution", "label"}),
    "formula": ({"text"}, {"description", "label"}),
    "statement": ({"text"}, {"label"}),
    "definition": ({"term", "text"}, {"label"}),
    "table": ({"headers", "rows"}, {"label"}),
    "figure": ({"figure_index"}, {"page", "caption", "text"}),
    "recap": ({"items"}, {"label"}),
}


def _chunk_explanation_source(text: str, max_chunk_chars: int = 1500) -> list[dict[str, str]]:
    """Split extracted text into stable citation units without dropping long paragraphs."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        remaining = paragraph
        while len(remaining) > max_chunk_chars:
            split_at = remaining.rfind(" ", 0, max_chunk_chars + 1)
            if split_at <= 0:
                split_at = max_chunk_chars
            pieces.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
        if remaining:
            pieces.append(remaining)

    chunks: list[dict[str, str]] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) + 2 > max_chunk_chars:
            chunks.append({"id": f"c{len(chunks) + 1}", "text": current})
            current = piece
        else:
            current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append({"id": f"c{len(chunks) + 1}", "text": current})
    return chunks


def _validate_explanation_blocks(
    blocks: list[object], source_ids: set[str]
) -> tuple[list[dict], list[str]]:
    valid: list[dict] = []
    errors: list[str] = []
    for index, value in enumerate(blocks):
        if not isinstance(value, dict):
            errors.append(f"block[{index}]: not an object")
            continue
        block_type = value.get("type")
        if not isinstance(block_type, str) or block_type not in _EXPLANATION_BLOCK_FIELDS:
            errors.append(f"block[{index}]: unknown type {block_type!r}")
            continue
        required, optional = _EXPLANATION_BLOCK_FIELDS[block_type]
        missing = [field for field in required if field not in value or value[field] is None]
        if missing:
            errors.append(f"block[{index}] ({block_type}): missing {missing}")
            continue

        clean = {
            key: field_value
            for key, field_value in value.items()
            if key in required | optional
        }
        shape_error = None
        for field in ("text", "term", "label", "language", "attribution", "description", "caption"):
            if field in clean and not isinstance(clean[field], str):
                shape_error = f"{field} must be a string"
                break
        for field in ("items", "steps", "headers"):
            if field in clean and (
                not isinstance(clean[field], list)
                or any(not isinstance(item, str) for item in clean[field])
            ):
                shape_error = f"{field} must be an array of strings"
                break
        if "rows" in clean and (
            not isinstance(clean["rows"], list)
            or any(
                not isinstance(row, list) or any(not isinstance(cell, str) for cell in row)
                for row in clean["rows"]
            )
        ):
            shape_error = "rows must be an array of string arrays"
        if block_type == "heading" and "level" in clean and clean["level"] not in (1, 2, 3):
            shape_error = "heading level must be 1, 2, or 3"
        if block_type == "figure" and (
            type(clean["figure_index"]) is not int or clean["figure_index"] < 1
        ):
            shape_error = "figure_index must be a positive integer"
        if block_type == "figure" and "page" in clean and (
            type(clean["page"]) is not int or clean["page"] < 1
        ):
            shape_error = "page must be a positive integer"
        if block_type == "calculation" and not clean.get("text") and not clean.get("steps"):
            shape_error = "calculation requires text or steps"
        if shape_error:
            errors.append(f"block[{index}] ({block_type}): {shape_error}")
            continue

        refs = value.get("source_refs")
        if isinstance(refs, list):
            clean["source_refs"] = [ref for ref in refs if isinstance(ref, str) and ref in source_ids]
        elif isinstance(refs, str) and refs in source_ids:
            clean["source_refs"] = [refs]
        clean["type"] = block_type
        valid.append(clean)
    return valid, errors


def _job_error_message(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    message = str(exc).strip()
    return message or exc.__class__.__name__


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
        self.jobs = SowUploadJobRepository(db)
        self.lesson_progress = StudyLessonProgressRepository(db)

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
        material = await self._create_material_from_text(
            current_user,
            title,
            content,
            exam_type,
            education_level,
        )
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
        material = await self._create_material_from_text(
            current_user,
            use_title,
            extracted_text,
            exam_type,
            education_level,
            original_file_data=data,
            file_mime_type=mime,
            page_count=page_count,
        )
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
        explanation = None
        if material.explanation_structure:
            try:
                explanation = json.loads(material.explanation_structure)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=500,
                    detail="Stored formatted explanation is invalid JSON.",
                ) from exc
        if isinstance(explanation, dict) and isinstance(explanation.get("content_blocks"), list):
            source_ids = {
                chunk["id"]
                for chunk in _chunk_explanation_source(material.content or "")
            }
            blocks, _ = _validate_explanation_blocks(explanation["content_blocks"], source_ids)
            if len(blocks) >= 3:
                explanation = {
                    "content_blocks": blocks,
                    "source_refs_present": any("source_refs" in block for block in blocks),
                }
            else:
                explanation = None
        if explanation is None:
            explanation = await self._build_explanation(
                material.content,
                material.education_level,
                material.exam_type,
            )
            material.explanation_structure = json.dumps(explanation)
            await self.materials.update(material)
        parsed = None
        if material.parsed_structure:
            try:
                parsed = json.loads(material.parsed_structure)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=500,
                    detail="Stored parsed material is invalid JSON.",
                ) from exc
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
        lesson_status = getattr(material, "lesson_status", None)
        has_lesson = bool(getattr(material, "lesson_structure", None))
        return {
            "id": material.id,
            "title": material.title,
            "exam_type": material.exam_type,
            "education_level": material.education_level,
            "content": material.content,
            "parsed_structure": parsed,
            "explanation_structure": explanation,
            "page_count": getattr(material, "page_count", 0) or 0,
            "figure_count": getattr(material, "figure_count", 0) or 0,
            "has_original_file": bool(getattr(material, "original_file_data", None)),
            "file_mime_type": getattr(material, "file_mime_type", None),
            "lesson_status": lesson_status,
            "lesson_error": getattr(material, "lesson_error", None),
            "has_lesson": has_lesson,
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


    async def _parse_structure(self, content: str) -> dict:
        response = await call_ai(SOW_PARSER_PROMPT.replace("{raw_text}", content[:50000]))
        try:
            parsed = await parse_json_response(response)
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not parse extracted study material: {exc}",
            ) from exc
        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=502,
                detail="Could not parse extracted study material: AI response must be a JSON object.",
            )
        return parsed

    async def _build_explanation(self, content: str, education_level: str | None, exam_type: str | None) -> dict:
        if not content or not content.strip():
            raise HTTPException(
                status_code=422,
                detail="Cannot format study material because no text was extracted.",
            )
        chunks = _chunk_explanation_source(content[:40000])
        if not chunks:
            raise HTTPException(
                status_code=422,
                detail="Cannot format study material because no text was extracted.",
            )
        source_ids = {chunk["id"] for chunk in chunks}
        source_context = "\n\n".join(f"[{chunk['id']}] {chunk['text']}" for chunk in chunks)
        prompt = EXPLANATION_PROMPT.replace(
            "{education_level}", education_level or "secondary"
        ).replace(
            "{subject}", exam_type or "General"
        ).replace(
            "{raw_text}", source_context
        )
        errors: list[str] = []
        for attempt in range(2):
            attempt_prompt = prompt
            if attempt and errors:
                attempt_prompt += (
                    "\n\nCorrect these validation errors and return corrected JSON only:\n"
                    + "\n".join(f"- {error}" for error in errors[:8])
                )
            response = await call_ai(attempt_prompt)
            try:
                data = await parse_json_response(response)
            except ValueError as exc:
                errors = [f"response was not valid JSON: {exc}"]
                continue
            if not isinstance(data, dict) or not isinstance(data.get("content_blocks"), list):
                errors = ["response must be an object with a content_blocks array"]
                continue
            blocks, errors = _validate_explanation_blocks(data["content_blocks"], source_ids)
            if len(blocks) >= 3:
                return {
                    "content_blocks": blocks,
                    "source_refs_present": any("source_refs" in block for block in blocks),
                }
            errors = errors or ["response must contain at least three valid content blocks"]
        details = "; ".join(errors[:8])
        logger.error("study.explanation invalid blocks after retry errors=%s", details)
        raise HTTPException(
            status_code=502,
            detail=f"Could not format extracted study material after retry: {details}",
        )

    async def _create_material_from_text(
        self, current_user: User, title: str | None, content: str, exam_type: str | None,
        education_level: str | None, original_file_data: bytes | None = None, file_mime_type: str | None = None, page_count: int = 0
    ) -> StudyMaterial:
        material_title = (title or "").strip() or "Untitled Material"
        material = StudyMaterial(
            user_id=current_user.id,
            title=material_title[:500],
            exam_type=exam_type,
            education_level=education_level,
            raw_input=content,
            content=content,
            parsed_structure=None,
            explanation_structure=None,
            original_file_data=original_file_data,
            file_mime_type=file_mime_type,
            page_count=page_count or 0,
        )
        await self.materials.create(material)
        material_id = material.id

        # Best-effort enrichment after persist: reload material in a fresh DB session for each step
        # so a closed/stale connection or AI timeout cannot poison the upload/session.
        from app.core.database import AsyncSessionLocal

        async def _load(mid: int) -> StudyMaterial | None:
            async with AsyncSessionLocal() as db:
                return await StudyMaterialRepository(db).get_by_id(mid, current_user.id)

        async def _save(mid: int, updater) -> None:
            async with AsyncSessionLocal() as db:
                repo = StudyMaterialRepository(db)
                m = await repo.get_by_id(mid, current_user.id)
                if not m:
                    return
                updater(m)
                await repo.update(m)

        parsed = None
        try:
            parsed = await self._parse_structure(content)
        except Exception as exc:
            logger.warning(
                "study.material.parse failed user=%s material_id=%s: %s",
                current_user.id, material_id, _job_error_message(exc),
            )
        if parsed is not None:
            def _apply_parsed(m: StudyMaterial):
                m.parsed_structure = json.dumps(parsed)
                if (not title or not str(title).strip()) and isinstance(parsed, dict) and parsed.get("title"):
                    m.title = str(parsed.get("title"))[:500]
            try:
                await _save(material_id, _apply_parsed)
            except Exception as exc:
                logger.warning("study.material.parse save failed material_id=%s: %s", material_id, _job_error_message(exc))

        explanation = None
        try:
            explanation = await self._build_explanation(content, education_level, exam_type)
        except Exception as exc:
            logger.warning(
                "study.material.explanation failed user=%s material_id=%s: %s",
                current_user.id, material_id, _job_error_message(exc),
            )
        if explanation is not None:
            try:
                await _save(material_id, lambda m: setattr(m, "explanation_structure", json.dumps(explanation)))
            except Exception as exc:
                logger.warning("study.material.explanation save failed material_id=%s: %s", material_id, _job_error_message(exc))

        # Best-effort interactive lesson generation (teaching flow)
        try:
            m_for_lesson = await _load(material_id)
            if m_for_lesson:
                async with AsyncSessionLocal() as db:
                    ctrl = StudyController(db)
                    await ctrl._generate_and_store_lesson(m_for_lesson, parsed)
        except Exception as exc:
            logger.warning(
                "study.material.lesson failed user=%s material_id=%s: %s",
                current_user.id, material_id, _job_error_message(exc),
            )
            try:
                await _save(material_id, lambda m: (setattr(m, "lesson_status", "failed"), setattr(m, "lesson_error", _job_error_message(exc)[:300])))
            except Exception:
                logger.warning("study.material.lesson status save failed material_id=%s", material_id)

        final = await _load(material_id)
        return final or material

    async def create_sow_text_job(self, current_user: User, text: str, exam_type: str | None, education_level: str | None) -> dict:
        job = SowUploadJob(id=str(uuid.uuid4()), user_id=current_user.id, status="queued", progress=0, stage="queued", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        await self.jobs.create(job)
        asyncio.create_task(self._run_sow_text_job(job.id, current_user.id, text, exam_type, education_level))
        return {"job_id": job.id, "status": "queued"}

    async def _run_sow_text_job(self, job_id: str, user_id: int, text: str, exam_type: str | None, education_level: str | None) -> None:
        from app.core.database import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as db:
                ctrl = StudyController(db)
                await ctrl.jobs.update_status(job_id, "processing", progress=20, stage="parsing")
                user = User(id=user_id)
                material = await ctrl._create_material_from_text(user, None, text, exam_type, education_level)
                await ctrl.jobs.update_status(job_id, "completed", progress=100, stage="completed", material_id=material.id)
        except Exception as exc:
            logger.exception("study.sow_text_job failed job=%s: %s", job_id, exc)
            try:
                async with AsyncSessionLocal() as db:
                    await SowUploadJobRepository(db).update_status(job_id, "failed", stage="failed", error_message=_job_error_message(exc)[:300])
            except Exception:
                logger.exception("study.sow_text_job failed to record failure job=%s", job_id)

    async def create_sow_file_job(
        self,
        current_user: User,
        data: bytes,
        filename: str,
        mime: str,
        title: str | None,
        exam_type: str | None,
        education_level: str | None,
        selected_pages: list[int] | None = None,
    ) -> dict:
        job = SowUploadJob(id=str(uuid.uuid4()), user_id=current_user.id, status="queued", progress=0, stage="queued", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        await self.jobs.create(job)
        asyncio.create_task(
            self._run_sow_file_job(
                job.id,
                current_user.id,
                data,
                filename,
                mime,
                title,
                exam_type,
                education_level,
                selected_pages,
            )
        )
        return {"job_id": job.id, "status": "queued"}

    async def _run_sow_file_job(
        self,
        job_id: str,
        user_id: int,
        data: bytes,
        filename: str,
        mime: str,
        title: str | None,
        exam_type: str | None,
        education_level: str | None,
        selected_pages: list[int] | None,
    ) -> None:
        from app.core.database import AsyncSessionLocal
        try:
            from app.services.study_file_service import extract_text

            async with AsyncSessionLocal() as db:
                ctrl = StudyController(db)
                await ctrl.jobs.update_status(job_id, "processing", progress=10, stage="reading_pages")
                extracted_text, page_count = extract_text(data, filename, mime, selected_pages)
                await ctrl.jobs.update_status(job_id, "processing", progress=30, stage="parsing")
                user = User(id=user_id)
                use_title = (title or "").strip() or (filename.rsplit(".", 1)[0] if "." in filename else filename) or "Uploaded material"
                material = await ctrl._create_material_from_text(user, use_title, extracted_text, exam_type, education_level, original_file_data=data, file_mime_type=mime, page_count=page_count)
                await ctrl.jobs.update_status(job_id, "completed", progress=100, stage="completed", material_id=material.id)
        except Exception as exc:
            logger.exception("study.sow_file_job failed job=%s: %s", job_id, exc)
            try:
                async with AsyncSessionLocal() as db:
                    error = _job_error_message(exc)
                    await SowUploadJobRepository(db).update_status(job_id, "failed", stage="failed", error_message=error[:300])
            except Exception:
                logger.exception("study.sow_file_job failed to record failure job=%s", job_id)

    async def create_sow_image_job(
        self,
        current_user: User,
        images: list[tuple[bytes, str, str]],
        source_pdf: bytes,
        title: str | None,
        exam_type: str | None,
        education_level: str | None,
    ) -> dict:
        job = SowUploadJob(id=str(uuid.uuid4()), user_id=current_user.id, status="queued", progress=0, stage="queued", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        await self.jobs.create(job)
        asyncio.create_task(
            self._run_sow_image_job(
                job.id,
                current_user.id,
                images,
                source_pdf,
                title,
                exam_type,
                education_level,
            )
        )
        return {"job_id": job.id, "status": "queued"}

    async def _run_sow_image_job(
        self,
        job_id: str,
        user_id: int,
        images: list[tuple[bytes, str, str]],
        source_pdf: bytes,
        title: str | None,
        exam_type: str | None,
        education_level: str | None,
    ) -> None:
        from app.core.database import AsyncSessionLocal

        async def update_job(status: str, **fields) -> None:
            async with AsyncSessionLocal() as db:
                await SowUploadJobRepository(db).update_status(job_id, status, **fields)

        try:
            await update_job("processing", progress=10, stage="reading_pages")
            text_pages = []
            for index, (data, filename, mime) in enumerate(images, start=1):
                text = await call_ai_vision(
                    data,
                    mime,
                    "Transcribe all readable text from this study page in reading order. Preserve headings, lists, equations, and table structure. Do not summarize or add information.",
                )
                if not text.strip():
                    raise ValueError(f"No text could be extracted from image {index} ({filename})")
                text_pages.append(f"[PAGE {index}: {filename}]\n{text.strip()}")
                progress = 10 + round(index / len(images) * 20)
                await update_job(
                    "processing",
                    progress=progress,
                    stage="reading_pages",
                )

            extracted_text = "\n\n".join(text_pages)
            await update_job("processing", progress=30, stage="parsing")
            async with AsyncSessionLocal() as db:
                ctrl = StudyController(db)
                user = User(id=user_id)
                fallback_title = images[0][1].rsplit(".", 1)[0] if images else "Uploaded material"
                material_title = (title or "").strip() or fallback_title
                material = await ctrl._create_material_from_text(
                    user,
                    material_title,
                    extracted_text,
                    exam_type,
                    education_level,
                    original_file_data=source_pdf,
                    file_mime_type="application/pdf",
                    page_count=len(images),
                )
                await ctrl.jobs.update_status(job_id, "completed", progress=100, stage="completed", material_id=material.id)
        except Exception as exc:
            logger.exception("study.sow_image_job failed job=%s: %s", job_id, exc)
            try:
                error = _job_error_message(exc)
                await update_job("failed", stage="failed", error_message=error[:300])
            except Exception:
                logger.exception("study.sow_image_job failed to record failure job=%s", job_id)

    async def get_sow_job(self, current_user: User, job_id: str) -> dict:
        job = await self.jobs.get_for_user(job_id, current_user.id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": job.id,
            "status": job.status,
            "material_id": job.material_id,
            "error": job.error_message,
            "progress": job.progress,
            "stage": job.stage,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }

    async def get_material_original_file(self, current_user: User, material_id: int) -> tuple[bytes, str | None]:
        material = await self._get_owned_material(current_user, material_id)
        if not material.original_file_data:
            raise HTTPException(status_code=404, detail="Original file not found")
        return material.original_file_data, material.file_mime_type


    # --- interactive lesson ---

    async def _generate_and_store_lesson(self, material: StudyMaterial, parsed: dict | None = None) -> dict | None:
        material.lesson_status = "generating"
        material.lesson_error = None
        await self.materials.update(material)
        try:
            parsed_obj = parsed
            if parsed_obj is None and material.parsed_structure:
                try:
                    parsed_obj = json.loads(material.parsed_structure)
                except Exception:
                    parsed_obj = None
            raw_text = (material.content or material.raw_input or "")
            prompt = LESSON_GENERATION_PROMPT.format(
                education_level=material.education_level or "secondary",
                subject=material.exam_type or "General",
                parsed=json.dumps(parsed_obj or {}, ensure_ascii=False)[:12000],
                raw_text=raw_text[:30000],
            )
            last_err = None
            lesson = None
            for attempt in range(2):
                use_prompt = prompt
                if attempt == 1:
                    # retry: compact, fewer segments, to avoid truncation
                    use_prompt = prompt + "\n\nIMPORTANT: Return compact JSON only. Limit to 3-4 segments total. Keep each field concise so the full response fits in one message."
                response = await call_ai(use_prompt, max_tokens=6000)
                try:
                    lesson = await parse_json_response(response)
                except Exception as exc:
                    last_err = exc
                    logger.warning("study.lesson.parse attempt=%s material_id=%s failed: %s", attempt + 1, material.id, _job_error_message(exc))
                    lesson = None
                    continue
                if not isinstance(lesson, dict):
                    last_err = ValueError("Lesson response must be a JSON object")
                    lesson = None
                    continue
                segments = lesson.get("segments")
                if not isinstance(segments, list) or not segments:
                    last_err = ValueError("Lesson must contain at least one segment")
                    lesson = None
                    continue
                lesson["segments"] = [s for s in segments if isinstance(s, dict)][:8]
                if not lesson["segments"]:
                    last_err = ValueError("Lesson segments are invalid")
                    lesson = None
                    continue
                break
            if lesson is None:
                raise last_err or ValueError("Lesson generation failed")

            if not isinstance(lesson.get("intro"), dict):
                lesson["intro"] = {
                    "title": material.title or "Lesson",
                    "goals": ["Understand the key ideas in this material."],
                    "why_it_matters": "This helps you learn and apply the topic.",
                    "prior_knowledge": [],
                    "overview": "We will go through the material in short, interactive parts.",
                }
            if not isinstance(lesson.get("outro"), dict):
                lesson["outro"] = {
                    "summary": ["Review the key points from each part."],
                    "common_pitfalls": [],
                    "next_steps": "Practice with questions or review the original material.",
                }
            for i, seg in enumerate(lesson["segments"]):
                seg.setdefault("index", i)
                seg.setdefault("title", f"Part {i + 1}")
            material.lesson_structure = json.dumps(lesson, ensure_ascii=False)
            material.lesson_status = "ready"
            material.lesson_error = None
            await self.materials.update(material)
            logger.info("study.lesson.ready material_id=%s segments=%s", material.id, len(lesson["segments"]))
            return lesson
        except Exception as exc:
            material.lesson_status = "failed"
            material.lesson_error = _job_error_message(exc)[:300]
            await self.materials.update(material)
            logger.warning("study.lesson.generate failed material_id=%s: %s", material.id, material.lesson_error)
            return None

    async def get_lesson(self, current_user: User, material_id: int) -> dict:
        material = await self._get_owned_material(current_user, material_id)
        lesson = None
        if material.lesson_structure:
            try:
                lesson = json.loads(material.lesson_structure)
            except Exception:
                lesson = None
        progress_row = await self.lesson_progress.get_or_create(current_user.id, material_id)
        try:
            states = json.loads(progress_row.segment_states) if progress_row.segment_states else {}
            if not isinstance(states, dict):
                states = {}
        except Exception:
            states = {}
        return {
            "material_id": material.id,
            "lesson_status": getattr(material, "lesson_status", None),
            "lesson_error": getattr(material, "lesson_error", None),
            "lesson": lesson,
            "progress": {
                "current_segment": progress_row.current_segment or 0,
                "segment_states": states,
                "completed": bool(progress_row.completed),
            },
        }

    async def generate_lesson_endpoint(self, current_user: User, material_id: int) -> dict:
        material = await self._get_owned_material(current_user, material_id)
        if not (material.content or material.raw_input):
            raise HTTPException(status_code=422, detail="Material has no extracted content to build a lesson from.")
        lesson = await self._generate_and_store_lesson(material)
        if lesson is None:
            raise HTTPException(status_code=502, detail=material.lesson_error or "Lesson generation failed. Please try again.")
        return await self.get_lesson(current_user, material_id)

    async def update_lesson_progress(
        self,
        current_user: User,
        material_id: int,
        current_segment: int,
        segment_states: dict | None,
        completed: bool | None,
    ) -> dict:
        await self._get_owned_material(current_user, material_id)
        row = await self.lesson_progress.get_or_create(current_user.id, material_id)
        states = None
        if segment_states is not None:
            states = segment_states
        else:
            try:
                states = json.loads(row.segment_states) if row.segment_states else {}
            except Exception:
                states = {}
        if current_segment < 0:
            current_segment = 0
        await self.lesson_progress.update(
            row, current_segment=current_segment, segment_states=states, completed=completed
        )
        return await self.get_lesson(current_user, material_id)

    async def check_lesson_answer(
        self, current_user: User, material_id: int, segment_index: int, item_type: str, answer: str
    ) -> dict:
        material = await self._get_owned_material(current_user, material_id)
        lesson = None
        if material.lesson_structure:
            try:
                lesson = json.loads(material.lesson_structure)
            except Exception:
                lesson = None
        if not lesson or not isinstance(lesson.get("segments"), list):
            raise HTTPException(status_code=404, detail="Lesson is not available for this material yet.")
        segments = lesson["segments"]
        if segment_index < 0 or segment_index >= len(segments):
            raise HTTPException(status_code=400, detail="Invalid lesson segment.")
        seg = segments[segment_index] if isinstance(segments[segment_index], dict) else {}
        micro_goal = seg.get("micro_goal") or seg.get("title") or ""
        if item_type == "guided":
            item = seg.get("guided_practice") or {}
            question = item.get("prompt") or ""
            expected = item.get("solution") or ""
            key_points = item.get("hint") or ""
            misconceptions = "[]"
        elif item_type == "independent":
            item = seg.get("independent_practice") or {}
            question = item.get("prompt") or ""
            expected = item.get("rubric") or ""
            key_points = json.dumps(expected, ensure_ascii=False) if isinstance(expected, list) else str(expected)
            misconceptions = "[]"
        else:
            item = seg.get("check") or {}
            question = item.get("question") or ""
            expected = item.get("expected_answer") or ""
            kp = item.get("key_points") or []
            key_points = json.dumps(kp, ensure_ascii=False) if isinstance(kp, list) else str(kp)
            misconceptions = json.dumps(item.get("misconceptions") or [], ensure_ascii=False)

        prompt = LESSON_CHECK_PROMPT.format(
            education_level=material.education_level or "secondary",
            subject=material.exam_type or "General",
            micro_goal=micro_goal,
            item_type=item_type,
            question=question,
            expected_answer=json.dumps(expected, ensure_ascii=False) if not isinstance(expected, str) else expected,
            key_points=key_points,
            misconceptions=misconceptions,
            answer=answer or "",
        )
        resp = await call_ai(prompt, max_tokens=1200)
        try:
            data = await parse_json_response(resp)
        except Exception:
            model_answer = expected if isinstance(expected, str) else json.dumps(expected, ensure_ascii=False)
            return {
                "correct": True if (answer or "").strip() else False,
                "feedback": "Good effort. Compare your answer with the model answer and key points for this step.",
                "misconception": None,
                "can_continue": bool((answer or "").strip()),
                "model_answer": model_answer,
            }
        model_answer = data.get("model_answer")
        if not model_answer:
            model_answer = expected if isinstance(expected, str) else json.dumps(expected, ensure_ascii=False)
        return {
            "correct": data.get("correct"),
            "feedback": data.get("feedback") or "Review the model answer and try to address the key points.",
            "misconception": data.get("misconception"),
            "can_continue": bool(data.get("can_continue")),
            "model_answer": model_answer,
        }

