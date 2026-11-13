/**
 * Offline storage for study assets and materials
 * Caches unlocked content and material metadata locally for offline access
 */

import * as SecureStore from "expo-secure-store";
import * as FileSystem from "expo-file-system";
// Legacy helpers for base64 writes - root export throws at runtime (SDK 54+)
import * as FileSystemLegacy from "expo-file-system/legacy";

import { cacheDirectory, documentDirectory } from "@/src/shared/lib/file-paths";

const CACHE_PREFIX = "study_asset_";
const CACHE_INDEX_KEY = "study_asset_index";
const MATERIAL_CACHE_PREFIX = "study_material_";
const MATERIAL_CACHE_INDEX_KEY = "study_material_index";
const MATERIAL_FILE_DIR = cacheDirectory + "study_files/";

// ── Upload drafts (converted PDF pages / picked files saved locally) ─────
// Saved BEFORE upload so AI/network failures don't force re-pick or re-convert.
// Deleted immediately on successful upload+parse. Stored in documentDirectory
// (persistent, not cache) so drafts survive cache clears and app restarts.
const DRAFT_INDEX_KEY = "study_upload_draft_index";
const DRAFT_PREFIX = "study_upload_draft_";
const DRAFT_DIR_NAME = "study_upload_drafts";

export type DraftPage = {
  page: number;
  /** Local file URI of the converted page image (PNG). */
  uri: string;
  width?: number;
  height?: number;
};

export type UploadDraft = {
  id: string;
  /** "pdf" | "image" | "document" */
  kind: "pdf" | "image" | "document";
  /** Local URI of the original picked file (copied into draft dir). */
  originalUri: string;
  name: string;
  mimeType: string;
  examType: string | null;
  educationLevel: string | null;
  /** Converted page images (PDF preview pages saved to disk). */
  pages: DraftPage[];
  selectedPages: number[];
  totalPages: number;
  status: "draft" | "uploading" | "processing" | "failed";
  error?: string | null;
  /** Server job id if upload was accepted (for retry/resume polling). */
  jobId?: string | null;
  createdAt: string;
  updatedAt: string;
};

type CachedAsset = {
  assetId: number;
  content: unknown;
  unlockedAt: string;
  materialId: number;
};

type CachedMaterial = {
  id: number;
  title: string;
  exam_type: string | null;
  asset_types: string[];
  created_at: string;
  cachedAt: string;
};

/**
 * Get cached asset index (list of cached asset IDs)
 */
async function getCacheIndex(): Promise<number[]> {
  try {
    const index = await SecureStore.getItemAsync(CACHE_INDEX_KEY);
    return index ? JSON.parse(index) : [];
  } catch {
    return [];
  }
}

/**
 * Update cache index
 */
async function updateCacheIndex(assetIds: number[]): Promise<void> {
  try {
    await SecureStore.setItemAsync(CACHE_INDEX_KEY, JSON.stringify(assetIds));
  } catch (error) {
    console.error("Failed to update cache index:", error);
  }
}

/**
 * Cache an unlocked asset
 */
export async function cacheAsset(
  assetId: number,
  content: unknown,
  materialId: number,
): Promise<void> {
  try {
    const cached: CachedAsset = {
      assetId,
      content,
      unlockedAt: new Date().toISOString(),
      materialId,
    };

    await SecureStore.setItemAsync(
      `${CACHE_PREFIX}${assetId}`,
      JSON.stringify(cached),
    );

    // Update index
    const index = await getCacheIndex();
    if (!index.includes(assetId)) {
      await updateCacheIndex([...index, assetId]);
    }
  } catch (error) {
    console.error("Failed to cache asset:", error);
    // Don't throw - caching is optional
  }
}

/**
 * Get cached asset
 */
export async function getCachedAsset(
  assetId: number,
): Promise<CachedAsset | null> {
  try {
    const cached = await SecureStore.getItemAsync(`${CACHE_PREFIX}${assetId}`);
    return cached ? JSON.parse(cached) : null;
  } catch (error) {
    console.error("Failed to get cached asset:", error);
    return null;
  }
}

/**
 * Check if asset is cached
 */
export async function isAssetCached(assetId: number): Promise<boolean> {
  try {
    const cached = await SecureStore.getItemAsync(`${CACHE_PREFIX}${assetId}`);
    return cached !== null;
  } catch {
    return false;
  }
}

/**
 * Get all cached assets
 */
export async function getAllCachedAssets(): Promise<CachedAsset[]> {
  try {
    const index = await getCacheIndex();
    const assets: CachedAsset[] = [];

    for (const assetId of index) {
      const cached = await getCachedAsset(assetId);
      if (cached) {
        assets.push(cached);
      }
    }

    return assets;
  } catch (error) {
    console.error("Failed to get all cached assets:", error);
    return [];
  }
}

/**
 * Clear cache for a specific asset
 */
export async function clearAssetCache(assetId: number): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(`${CACHE_PREFIX}${assetId}`);

    // Update index
    const index = await getCacheIndex();
    await updateCacheIndex(index.filter((id) => id !== assetId));
  } catch (error) {
    console.error("Failed to clear asset cache:", error);
  }
}

/**
 * Clear all cached assets
 */
export async function clearAllCache(): Promise<void> {
  try {
    const index = await getCacheIndex();

    for (const assetId of index) {
      await SecureStore.deleteItemAsync(`${CACHE_PREFIX}${assetId}`);
    }

    await SecureStore.deleteItemAsync(CACHE_INDEX_KEY);
  } catch (error) {
    console.error("Failed to clear all cache:", error);
  }
}

/**
 * Get cache size (number of cached assets)
 */
export async function getCacheSize(): Promise<number> {
  try {
    const index = await getCacheIndex();
    return index.length;
  } catch {
    return 0;
  }
}

// ── Material metadata cache ──────────────────────────────────────────

async function getMaterialCacheIndex(): Promise<number[]> {
  try {
    const index = await SecureStore.getItemAsync(MATERIAL_CACHE_INDEX_KEY);
    return index ? JSON.parse(index) : [];
  } catch {
    return [];
  }
}

async function updateMaterialCacheIndex(materialIds: number[]): Promise<void> {
  try {
    await SecureStore.setItemAsync(
      MATERIAL_CACHE_INDEX_KEY,
      JSON.stringify(materialIds),
    );
  } catch (error) {
    console.error("Failed to update material cache index:", error);
  }
}

export async function cacheMaterialMetadata(material: {
  id: number;
  title: string;
  exam_type: string | null;
  asset_types: string[];
  created_at: string;
}): Promise<void> {
  try {
    const cached: CachedMaterial = {
      id: material.id,
      title: material.title,
      exam_type: material.exam_type,
      asset_types: material.asset_types || [],
      created_at: material.created_at,
      cachedAt: new Date().toISOString(),
    };

    await SecureStore.setItemAsync(
      `${MATERIAL_CACHE_PREFIX}${material.id}`,
      JSON.stringify(cached),
    );

    const index = await getMaterialCacheIndex();
    if (!index.includes(material.id)) {
      await updateMaterialCacheIndex([...index, material.id]);
    }
  } catch (error) {
    console.error("Failed to cache material metadata:", error);
  }
}

export async function getCachedMaterialMetadata(
  materialId: number,
): Promise<CachedMaterial | null> {
  try {
    const cached = await SecureStore.getItemAsync(
      `${MATERIAL_CACHE_PREFIX}${materialId}`,
    );
    return cached ? JSON.parse(cached) : null;
  } catch (error) {
    console.error("Failed to get cached material metadata:", error);
    return null;
  }
}

export async function getAllCachedMaterialMetadata(): Promise<
  CachedMaterial[]
> {
  try {
    const index = await getMaterialCacheIndex();
    const materials: CachedMaterial[] = [];

    for (const materialId of index) {
      const cached = await getCachedMaterialMetadata(materialId);
      if (cached) {
        materials.push(cached);
      }
    }

    return materials;
  } catch (error) {
    console.error("Failed to get all cached materials:", error);
    return [];
  }
}

export async function clearMaterialCache(materialId: number): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(`${MATERIAL_CACHE_PREFIX}${materialId}`);

    const index = await getMaterialCacheIndex();
    await updateMaterialCacheIndex(index.filter((id) => id !== materialId));
  } catch (error) {
    console.error("Failed to clear material cache:", error);
  }
}

export async function clearAllMaterialCache(): Promise<void> {
  try {
    const index = await getMaterialCacheIndex();

    for (const materialId of index) {
      await SecureStore.deleteItemAsync(
        `${MATERIAL_CACHE_PREFIX}${materialId}`,
      );
    }

    await SecureStore.deleteItemAsync(MATERIAL_CACHE_INDEX_KEY);
  } catch (error) {
    console.error("Failed to clear all material cache:", error);
  }
}

// ── Original file bytes cache ────────────────────────────────────────

function ensureMaterialFileDir(): void {
  const dir = new FileSystem.Directory(FileSystem.Paths.cache, "study_files");
  if (!dir.exists) {
    dir.create({ intermediates: true });
  }
}

export async function cacheMaterialFile(
  materialId: number,
  base64Data: string,
  mimeType: string,
): Promise<void> {
  try {
    ensureMaterialFileDir();
    const ext = mimeType.split("/")[1]?.split(";")[0] || "bin";
    const dir = new FileSystem.Directory(FileSystem.Paths.cache, "study_files");
    const file = new FileSystem.File(dir, `${materialId}.${ext}`);

    // Convert base64 to Uint8Array and write
    const binaryString = atob(base64Data);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    file.write(bytes);
  } catch (error) {
    console.error("Failed to cache material file:", error);
  }
}

export async function getCachedMaterialFileUri(
  materialId: number,
  mimeType?: string | null,
): Promise<string | null> {
  try {
    const dir = new FileSystem.Directory(FileSystem.Paths.cache, "study_files");
    if (!dir.exists) return null;

    const files = dir.list();
    const matchingFile = files.find(
      (item) =>
        item instanceof FileSystem.File &&
        item.name.startsWith(`${materialId}.`),
    );
    if (!matchingFile) return null;

    return matchingFile.uri;
  } catch (error) {
    console.error("Failed to get cached material file:", error);
    return null;
  }
}

export async function isMaterialFileCached(
  materialId: number,
): Promise<boolean> {
  try {
    const uri = await getCachedMaterialFileUri(materialId);
    return uri !== null;
  } catch {
    return false;
  }
}

export async function clearMaterialFileCache(
  materialId: number,
): Promise<void> {
  try {
    const uri = await getCachedMaterialFileUri(materialId);
    if (uri) {
      const file = new FileSystem.File(uri);
      file.delete();
    }
  } catch (error) {
    console.error("Failed to clear material file cache:", error);
  }
}

export async function clearAllMaterialFileCache(): Promise<void> {
  try {
    const dir = new FileSystem.Directory(FileSystem.Paths.cache, "study_files");
    if (dir.exists) {
      dir.delete();
    }
  } catch (error) {
    console.error("Failed to clear all material file cache:", error);
  }
}

// ── Upload draft helpers ──────────────────────────────────────────────────

function randomId(): string {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const c: any = globalThis.crypto ?? require("expo-crypto");
    if (c?.randomUUID) return c.randomUUID();
  } catch {
    // fall through
  }
  return "draft_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 10);
}

function ensureDraftRoot(): string {
  const dir = new FileSystem.Directory(FileSystem.Paths.document, DRAFT_DIR_NAME);
  if (!dir.exists) dir.create({ intermediates: true });
  return dir.uri;
}

function draftDirUri(id: string): string {
  ensureDraftRoot();
  return `${documentDirectory}${DRAFT_DIR_NAME}/${id}/`;
}

function ensureDraftDir(id: string): string {
  const uri = draftDirUri(id);
  const dir = new FileSystem.Directory(uri);
  if (!dir.exists) dir.create({ intermediates: true });
  return uri;
}

async function getDraftIndex(): Promise<string[]> {
  try {
    const raw = await SecureStore.getItemAsync(DRAFT_INDEX_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

async function setDraftIndex(ids: string[]): Promise<void> {
  try {
    await SecureStore.setItemAsync(DRAFT_INDEX_KEY, JSON.stringify(ids));
  } catch (e) {
    console.error("Failed to update draft index:", e);
  }
}

export async function getUploadDraft(id: string): Promise<UploadDraft | null> {
  try {
    const raw = await SecureStore.getItemAsync(`${DRAFT_PREFIX}${id}`);
    return raw ? (JSON.parse(raw) as UploadDraft) : null;
  } catch {
    return null;
  }
}

async function putUploadDraft(draft: UploadDraft): Promise<void> {
  draft.updatedAt = new Date().toISOString();
  await SecureStore.setItemAsync(`${DRAFT_PREFIX}${draft.id}`, JSON.stringify(draft));
  const idx = await getDraftIndex();
  if (!idx.includes(draft.id)) await setDraftIndex([draft.id, ...idx]);
}

export async function getAllUploadDrafts(): Promise<UploadDraft[]> {
  try {
    const idx = await getDraftIndex();
    const out: UploadDraft[] = [];
    const live: string[] = [];
    for (const id of idx) {
      const d = await getUploadDraft(id);
      if (d) {
        out.push(d);
        live.push(id);
      }
    }
    if (live.length !== idx.length) await setDraftIndex(live);
    return out.sort((a, b) => (b.updatedAt > a.updatedAt ? 1 : -1));
  } catch {
    return [];
  }
}

export async function updateUploadDraft(
  id: string,
  patch: Partial<UploadDraft>,
): Promise<UploadDraft | null> {
  const cur = await getUploadDraft(id);
  if (!cur) return null;
  const next = { ...cur, ...patch, id: cur.id, updatedAt: new Date().toISOString() };
  await putUploadDraft(next);
  return next;
}

/**
 * Save a converted PDF (preview page images) as a local draft BEFORE upload.
 * Writes each page's base64 PNG to documentDirectory so it survives app
 * restart/kick-outs and can be retried without re-conversion or re-pick.
 */
export async function savePdfUploadDraft(params: {
  originalFile: { uri: string; name: string; type: string };
  pages: Array<{ page: number; image_base64: string; width?: number; height?: number }>;
  selectedPages: number[];
  examType: string | null;
  educationLevel: string | null;
}): Promise<UploadDraft> {
  const id = randomId();
  const dir = ensureDraftDir(id);

  // Persist the original picked file into the draft dir (best effort).
  let originalUri = params.originalFile.uri;
  try {
    const safeName = (params.originalFile.name || "source.pdf").replace(/[^a-zA-Z0-9._-]+/g, "_");
    const dest = `${dir}${safeName}`;
    await FileSystemLegacy.copyAsync({ from: params.originalFile.uri, to: dest });
    originalUri = dest;
  } catch (e) {
    console.warn("[draft] original copy failed, keeping picker uri", e);
  }

  // Persist converted page images (base64 PNG -> file).
  const pages: DraftPage[] = [];
  for (const p of params.pages || []) {
    try {
      if (!p?.image_base64) continue;
      const pageUri = `${dir}page-${p.page}.png`;
      await FileSystemLegacy.writeAsStringAsync(pageUri, p.image_base64, {
        encoding: FileSystemLegacy.EncodingType.Base64,
      });
      pages.push({ page: p.page, uri: pageUri, width: p.width, height: p.height });
    } catch (e) {
      console.warn("[draft] failed to write page", p?.page, e);
    }
  }

  const draft: UploadDraft = {
    id,
    kind: "pdf",
    originalUri,
    name: params.originalFile.name,
    mimeType: params.originalFile.type || "application/pdf",
    examType: params.examType ?? null,
    educationLevel: params.educationLevel ?? null,
    pages,
    selectedPages: params.selectedPages?.length ? [...params.selectedPages] : pages.map((p) => p.page),
    totalPages: pages.length,
    status: "draft",
    error: null,
    jobId: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  await putUploadDraft(draft);
  return draft;
}

/** Read a draft page image back as base64 (for retry upload if needed). */
export async function readDraftPageBase64(uri: string): Promise<string | null> {
  try {
    return await FileSystemLegacy.readAsStringAsync(uri, {
      encoding: FileSystemLegacy.EncodingType.Base64,
    });
  } catch (e) {
    console.warn("[draft] read page failed", e);
    return null;
  }
}

/** Delete a draft and its files (call on success or user discard). */
export async function deleteUploadDraft(id: string): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(`${DRAFT_PREFIX}${id}`);
  } catch {}
  try {
    const idx = await getDraftIndex();
    await setDraftIndex(idx.filter((x) => x !== id));
  } catch {}
  try {
    const dir = new FileSystem.Directory(draftDirUri(id));
    if (dir.exists) dir.delete();
  } catch (e) {
    console.warn("[draft] delete dir failed", e);
  }
}
