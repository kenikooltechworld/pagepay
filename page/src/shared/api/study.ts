import { apiFetch, parseApiError } from "@/src/shared/api/client";

export type MaterialSummary = {
  id: number;
  title: string;
  exam_type: string | null;
  asset_types: string[];
  created_at: string;
};

export type AssetItem = {
  id: number;
  asset_type: "mcq" | "flashcard" | "essay" | string;
  topic: string | null;
  points_to_unlock: number;
  unlocked: boolean;
  created_at: string;
  content?: any;
};

export type MaterialDetail = {
  id: number;
  title: string;
  exam_type: string | null;
  education_level: string | null;
  content: string | null;
  parsed_structure: any;
  assets: AssetItem[];
  created_at: string;
};

export type GenerateAssetInput = {
  material_id: number;
  asset_type: "mcq" | "flashcard" | "essay";
  count: number;
  topic?: string | null;
  difficulty: "easy" | "medium" | "hard";
};

export type GenerateAssetResponse = {
  material_id: number;
  asset_id: number;
  asset_type: string;
  topic: string | null;
  points_to_unlock: number;
  unlocked: boolean;
  message: string | null;
};

export type UnlockResponse = {
  unlocked: boolean;
  asset_id: number;
  material_id: number;
  points_spent: number;
  new_sp_balance: number;
  content: any;
  method: string;
};

export type EssayReviewResponse = {
  correct: boolean;
  feedback: string;
  score: number | null;
  suggestions: string[];
};

export async function listMaterials(): Promise<MaterialSummary[]> {
  const res = await apiFetch("/study/materials");
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load materials"));
  return (await res.json()) as MaterialSummary[];
}

export async function getMaterial(id: number): Promise<MaterialDetail> {
  const res = await apiFetch(`/study/materials/${id}`);
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load material"));
  return (await res.json()) as MaterialDetail;
}

export async function createMaterial(input: {
  title: string;
  content: string;
  exam_type?: string | null;
  education_level?: string | null;
}): Promise<MaterialSummary> {
  const res = await apiFetch("/study/materials", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to create material"));
  return (await res.json()) as MaterialSummary;
}

export async function uploadMaterialFile(input: {
  file: { uri: string; name: string; type?: string };
  title?: string;
  exam_type?: string;
  education_level?: string;
}): Promise<MaterialSummary> {
  const form = new FormData();
  form.append("file", {
    uri: input.file.uri,
    name: input.file.name,
    type: input.file.type || "application/octet-stream",
  } as any);
  if (input.title) form.append("title", input.title);
  if (input.exam_type) form.append("exam_type", input.exam_type);
  if (input.education_level) form.append("education_level", input.education_level);
  const res = await apiFetch("/study/materials/upload", {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to upload material"));
  return (await res.json()) as MaterialSummary;
}

export async function updateMaterial(
  id: number,
  input: { title?: string; content?: string; exam_type?: string | null; education_level?: string | null }
): Promise<MaterialSummary> {
  const res = await apiFetch(`/study/materials/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to update material"));
  return (await res.json()) as MaterialSummary;
}

export async function deleteMaterial(id: number): Promise<void> {
  const res = await apiFetch(`/study/materials/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to delete material"));
}

export async function generateAsset(input: GenerateAssetInput): Promise<GenerateAssetResponse> {
  const res = await apiFetch("/study/generate", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to generate asset"));
  return (await res.json()) as GenerateAssetResponse;
}

export async function updateAsset(id: number, input: { topic?: string | null }): Promise<AssetItem> {
  const res = await apiFetch(`/study/assets/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to update asset"));
  return (await res.json()) as AssetItem;
}

export async function deleteAsset(id: number): Promise<void> {
  const res = await apiFetch(`/study/assets/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to delete asset"));
}

export async function unlockAsset(id: number): Promise<UnlockResponse> {
  const res = await apiFetch(`/study/assets/${id}/unlock`, { method: "POST" });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to unlock asset"));
  return (await res.json()) as UnlockResponse;
}

export async function submitEssay(input: {
  material_id: number;
  essay: string;
  topic?: string | null;
  asset_id?: number | null;
  question_index?: number;
}): Promise<EssayReviewResponse> {
  const res = await apiFetch("/study/essay/submit", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to submit essay"));
  return (await res.json()) as EssayReviewResponse;
}
