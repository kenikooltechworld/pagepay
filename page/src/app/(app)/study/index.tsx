import { useCallback, useEffect, useState } from "react";
import { Alert, Pressable, RefreshControl, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import * as DocumentPicker from "expo-document-picker";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { Fonts, PagePay } from "@/constants/theme";
import { EDUCATION_LEVELS, type EducationLevel } from "@/src/features/study/api";
import {
  deleteMaterial,
  previewSowPdf,
  listMaterials,
  pollSowJob,
  uploadSowDocument,
  uploadSowImages,
  uploadSowText,
  type MaterialSummary,
  type SowJobStatus,
} from "@/src/shared/api/study";
import { EXAM_TYPES } from "@/src/shared/lib/exam-types";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";
import { useImagePicker } from "@/src/shared/hooks/use-image-picker";
import {
  deleteUploadDraft,
  getAllUploadDrafts,
  savePdfUploadDraft,
  updateUploadDraft,
  type UploadDraft,
} from "@/src/features/study/storage";

type PickedFile = { uri: string; name: string; type: string };
type PdfPreviewItem = PickedFile & {
  page: number;
  width: number;
  height: number;
  is_scan: boolean;
  image_base64?: string;
};

function isPdf(file: PickedFile) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

function stageLabel(s?: string | null) {
  switch (s) {
    case "queued":
      return "Queued";
    case "parsing":
      return "Parsing material";
    case "reading_pages":
      return "Reading pages";
    case "saving":
      return "Saving";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return s ? s.replace(/_/g, " ") : "Processing";
  }
}

export default function StudyIndex() {
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [refreshing, setRefreshing] = useState(false);
  const [content, setContent] = useState("");
  const [examType, setExamType] = useState<string | null>(null);
  const [educationLevel, setEducationLevel] = useState<EducationLevel>("primary");
  const [job, setJob] = useState<SowJobStatus | null>(null);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [pdfPreviewLoading, setPdfPreviewLoading] = useState(false);
  const [pdfPreviewFile, setPdfPreviewFile] = useState<PickedFile | null>(null);
  const [pdfPreviewPages, setPdfPreviewPages] = useState<PdfPreviewItem[]>([]);
  const [selectedPdfPages, setSelectedPdfPages] = useState<number[]>([]);
  const [activeDraft, setActiveDraft] = useState<UploadDraft | null>(null);
  const [uploadDrafts, setUploadDrafts] = useState<UploadDraft[]>([]);
  const [selectedImages, setSelectedImages] = useState<PickedFile[]>([]);
  const { pickImages, takePhoto } = useImagePicker();

  const q = useQuery({ queryKey: ["study", "materials"], queryFn: listMaterials });

  const refreshDrafts = useCallback(async () => {
    setUploadDrafts(await getAllUploadDrafts());
  }, []);

  const persistDraftUpdate = useCallback(async (id: string, patch: Partial<UploadDraft>) => {
    try {
      const updated = await updateUploadDraft(id, patch);
      if (!updated) throw new Error("The saved draft no longer exists.");
      setActiveDraft(updated);
      await refreshDrafts();
      return true;
    } catch (e: unknown) {
      toast({
        title: "Draft update failed",
        description: e instanceof Error ? e.message : "The saved draft could not be updated.",
        variant: "destructive",
      });
      return false;
    }
  }, [refreshDrafts, toast]);

  useEffect(() => {
    void refreshDrafts();
  }, [refreshDrafts]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await q.refetch();
    } finally {
      setRefreshing(false);
    }
  }, [q]);

  const deleteMut = useMutation({
    mutationFn: deleteMaterial,
    onSuccess: () => {
      toast({ title: "Material deleted", variant: "success" });
      void qc.invalidateQueries({ queryKey: ["study", "materials"] });
    },
    onError: (e: Error) => toast({ title: "Delete failed", description: e.message, variant: "destructive" }),
  });

  const runJob = async (jobId: string, successTitle: string) => {
    const final = await pollSowJob(jobId, {
      onTick: (s) => setJob(s),
    });
    if (final.status === "failed") {
      throw new Error(final.error || "Processing failed");
    }
    setJob(final);
    toast({ title: successTitle, variant: "success" });
    await qc.invalidateQueries({ queryKey: ["study", "materials"] });
    return final;
  };

  const createAsync = async () => {
    const text = content.trim();
    if (text.length < 10 || text.length > 50_000 || busy) return;
    setBusy(true);
    setUploadPercent(null);
    setJob({ job_id: "", status: "queued", progress: 0, stage: "queued" });
    try {
      const accepted = await uploadSowText({
        text,
        exam_type: examType,
        education_level: educationLevel,
      });
      setJob({ job_id: accepted.job_id, status: accepted.status, progress: 5, stage: "queued" });
      const final = await runJob(accepted.job_id, "Material created");
      setContent("");
      if (final.material_id) router.push(`/(app)/study/${final.material_id}` as any);
    } catch (e: any) {
      toast({ title: "Create failed", description: e?.message || "Failed", variant: "destructive" });
      setJob((j) => j ? { ...j, status: "failed", error: e?.message || "Failed" } : j);
    } finally {
      setBusy(false);
      setUploadPercent(null);
    }
  };

  const uploadDocument = async (file: PickedFile, selectedPages?: number[], draft?: UploadDraft | null) => {
    setBusy(true);
    setUploadPercent(0);
    setJob({ job_id: "", status: "queued", progress: 0, stage: "queued" });
    try {
      if (draft) {
        if (!await persistDraftUpdate(draft.id, { status: "uploading", error: null })) return;
      }
      const accepted = await uploadSowDocument({
        file,
        exam_type: examType || undefined,
        education_level: educationLevel,
        selected_pages: selectedPages,
        onProgress: (loaded, total) => {
          if (total > 0) setUploadPercent(Math.round((loaded / total) * 100));
        },
      });
      setUploadPercent(100);
      setJob({ job_id: accepted.job_id, status: accepted.status, progress: 10, stage: "queued" });
      if (draft) {
        await persistDraftUpdate(draft.id, { status: "processing", jobId: accepted.job_id });
      }
      const final = await runJob(accepted.job_id, "Material uploaded");
      if (draft) {
        await deleteUploadDraft(draft.id);
        setActiveDraft(null);
        await refreshDrafts();
      }
      setPdfPreviewFile(null);
      setPdfPreviewPages([]);
      setSelectedPdfPages([]);
      if (final.material_id) router.push(`/(app)/study/${final.material_id}` as any);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Upload failed";
      if (draft) {
        await persistDraftUpdate(draft.id, { status: "failed", error: message });
      }
      toast({ title: "Upload failed", description: message, variant: "destructive" });
      setJob((current) => current ? { ...current, status: "failed", error: message } : current);
    } finally {
      setBusy(false);
      setUploadPercent(null);
    }
  };

  const pickFile = async () => {
    if (busy) return;
    const res = await DocumentPicker.getDocumentAsync({
      type: ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown"],
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (res.canceled || !res.assets?.[0]) return;
    const a = res.assets[0];
    const file = {
      uri: a.uri,
      name: a.name || "material",
      type: a.mimeType || "application/octet-stream",
    };
    setPdfPreviewFile(null);
    setPdfPreviewPages([]);
    setSelectedPdfPages([]);
    if (!isPdf(file)) {
      setActiveDraft(null);
      await uploadDocument(file);
      return;
    }

    setSelectedImages([]);
    setActiveDraft(null);
    setPdfPreviewLoading(true);
    setBusy(true);
    try {
      const preview = await previewSowPdf(file);
      const allPages = preview.pages.map((page) => page.page);
      let draft: UploadDraft | null = null;
      try {
        draft = await savePdfUploadDraft({
          originalFile: file,
          pages: preview.pages,
          selectedPages: allPages,
          title: null,
          examType,
          educationLevel,
        });
      } catch (e: unknown) {
        toast({
          title: "Draft not saved",
          description: `${e instanceof Error ? e.message : "Storage is unavailable."} You can still upload it now, but it will not be resumable after closing the app.`,
          variant: "destructive",
        });
      }
      setActiveDraft(draft);
      setPdfPreviewFile(draft ? {
        uri: draft.originalUri,
        name: draft.name,
        type: draft.mimeType,
      } : file);
      setPdfPreviewPages(draft?.pages.length
        ? draft.pages.map((page) => ({
            ...page,
            width: page.width ?? 0,
            height: page.height ?? 0,
            name: draft.name,
            type: "image/png",
            is_scan: false,
          }))
        : preview.pages.map((page) => ({
            ...page,
            uri: `data:image/png;base64,${page.image_base64}`,
            name: file.name,
            type: "image/png",
          })));
      setSelectedPdfPages(allPages);
      if (draft) await refreshDrafts();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to preview PDF";
      toast({ title: "PDF preview failed", description: message, variant: "destructive" });
    } finally {
      setBusy(false);
      setPdfPreviewLoading(false);
    }
  };

  const resumeDraft = (draft: UploadDraft) => {
    if (draft.status === "processing" && draft.jobId) {
      void resumeProcessingDraft(draft);
      return;
    }
    setActiveDraft(draft);
    setPdfPreviewFile({
      uri: draft.originalUri,
      name: draft.name,
      type: draft.mimeType,
    });
    setPdfPreviewPages(draft.pages.map((page) => ({
      ...page,
      width: page.width ?? 0,
      height: page.height ?? 0,
      name: draft.name,
      type: "image/png",
      is_scan: false,
    })));
    setSelectedPdfPages(draft.selectedPages);
    setExamType(draft.examType);
    setEducationLevel(
      EDUCATION_LEVELS.find((option) => option.value === draft.educationLevel)?.value ?? "primary",
    );
  };

  const resumeProcessingDraft = async (draft: UploadDraft) => {
    if (!draft.jobId || busy) return;
    setBusy(true);
    setJob({ job_id: draft.jobId, status: "processing", progress: 10, stage: "queued" });
    try {
      const final = await runJob(draft.jobId, "Material uploaded");
      await deleteUploadDraft(draft.id);
      await refreshDrafts();
      if (final.material_id) router.push(`/(app)/study/${final.material_id}` as any);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Could not resume processing";
      await persistDraftUpdate(draft.id, { status: "failed", error: message });
      toast({ title: "Resume failed", description: message, variant: "destructive" });
      setJob((current) => current ? { ...current, status: "failed", error: message } : current);
    } finally {
      setBusy(false);
    }
  };

  const togglePdfPage = async (pageNumber: number) => {
    const next = selectedPdfPages.includes(pageNumber)
      ? selectedPdfPages.filter((page) => page !== pageNumber)
      : [...selectedPdfPages, pageNumber].sort((a, b) => a - b);
    setSelectedPdfPages(next);
    if (activeDraft) {
      await persistDraftUpdate(activeDraft.id, { selectedPages: next });
    }
  };

  const selectAllPdfPages = async (selected: boolean) => {
    const next = selected ? pdfPreviewPages.map((page) => page.page) : [];
    setSelectedPdfPages(next);
    if (activeDraft) {
      await persistDraftUpdate(activeDraft.id, { selectedPages: next });
    }
  };

  const discardDraft = (draft: UploadDraft) => {
    Alert.alert("Discard upload draft?", `Remove the saved PDF draft "${draft.name}" from this device?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Discard",
        style: "destructive",
        onPress: () => {
          void deleteUploadDraft(draft.id).then(async () => {
            if (activeDraft?.id === draft.id) {
              setActiveDraft(null);
              setPdfPreviewFile(null);
              setPdfPreviewPages([]);
              setSelectedPdfPages([]);
            }
            await refreshDrafts();
          });
        },
      },
    ]);
  };

  const pickImagePages = async () => {
    if (busy) return;
    try {
      const files = await pickImages();
      if (!files) return;
      if (files.length > 10) {
        toast({ title: "Too many pages", description: "Choose up to 10 photos per material.", variant: "destructive" });
        return;
      }
      setActiveDraft(null);
      setSelectedImages(files.map(({ uri, name, type }) => ({ uri, name, type })));
      setPdfPreviewFile(null);
      setPdfPreviewPages([]);
      setSelectedPdfPages([]);
    } catch (e: unknown) {
      toast({ title: "Photo selection failed", description: e instanceof Error ? e.message : "Try again.", variant: "destructive" });
    }
  };

  const capturePage = async () => {
    if (busy) return;
    if (selectedImages.length >= 10) {
      toast({ title: "Page limit reached", description: "A material can contain up to 10 photos.", variant: "destructive" });
      return;
    }
    try {
      const file = await takePhoto();
      if (file) {
        setActiveDraft(null);
        setSelectedImages((current) => [...current, file]);
        setPdfPreviewFile(null);
        setPdfPreviewPages([]);
        setSelectedPdfPages([]);
      }
    } catch (e: unknown) {
      toast({ title: "Camera unavailable", description: e instanceof Error ? e.message : "Try again.", variant: "destructive" });
    }
  };

  const uploadImagePages = async () => {
    if (busy || selectedImages.length === 0) return;
    setBusy(true);
    setUploadPercent(0);
    setJob({ job_id: "", status: "queued", progress: 0, stage: "queued" });
    try {
      const accepted = await uploadSowImages({
        files: selectedImages,
        exam_type: examType || undefined,
        education_level: educationLevel,
        onProgress: (loaded, total) => {
          if (total > 0) setUploadPercent(Math.round((loaded / total) * 100));
        },
      });
      setUploadPercent(100);
      setJob({ job_id: accepted.job_id, status: accepted.status, progress: 10, stage: "queued" });
      const final = await runJob(accepted.job_id, "Photos processed");
      setSelectedImages([]);
      if (final.material_id) router.push(`/(app)/study/${final.material_id}` as any);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Photo processing failed";
      toast({ title: "Photo upload failed", description: message, variant: "destructive" });
      setJob((current) => current ? { ...current, status: "failed", error: message } : current);
    } finally {
      setBusy(false);
      setUploadPercent(null);
    }
  };

  const confirmDelete = (m: MaterialSummary) => {
    Alert.alert("Delete material?", `Delete "${m.title}" and all its assets/unlocks? This cannot be undone.`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => deleteMut.mutate(m.id) },
    ]);
  };

  const canCreate = content.trim().length >= 10 && content.trim().length <= 50_000 && !busy;
  const jobProgress = job?.status === "failed" ? 100 : Math.max(0, Math.min(100, job?.progress ?? (busy ? 5 : 0)));

  return (
    <View className="flex-1 bg-background" style={{ backgroundColor: tokens.paper }}>
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Study" tokens={tokens} />
        <ScrollView
          className="flex-1"
          contentContainerClassName="gap-5 px-4 py-5 pb-10"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={tokens.mint} />}
          showsVerticalScrollIndicator={false}
        >
          <Card className="overflow-hidden rounded-2xl border-dashed border-border p-0">
            <CardContent className="gap-4 p-4">
              <View className="flex-row items-start gap-3">
                <View className="h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
                  <Ionicons name="cloud-upload-outline" size={22} color={tokens.mint} />
                </View>
                <View className="flex-1 gap-1">
                  <Text
                    className="text-lg font-semibold text-foreground"
                    style={{ fontFamily: Fonts.editorialSemiBold as string }}
                  >
                    Create a study material
                  </Text>
                  <Text className="text-sm leading-5 text-muted-foreground">
                    Paste your notes or upload course material to build a study resource.
                  </Text>
                </View>
              </View>

              <View className="gap-2">
                <Text className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Exam type
                </Text>
                <View className="flex-row flex-wrap gap-2">
                  {EXAM_TYPES.map((option) => {
                    const selected = examType === option.key;
                    return (
                      <Pressable
                        key={option.key}
                        onPress={() => {
                          const nextExamType = selected ? null : option.key;
                          setExamType(nextExamType);
                          if (activeDraft) void persistDraftUpdate(activeDraft.id, { examType: nextExamType });
                        }}
                        accessibilityRole="button"
                        accessibilityState={{ selected }}
                        className={`rounded-full border px-3 py-1.5 ${selected ? "border-primary bg-primary/10" : "border-border bg-background"}`}
                      >
                        <Text className={`text-xs font-medium ${selected ? "text-primary" : "text-muted-foreground"}`}>
                          {option.label}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
              </View>

              <View className="gap-2">
                <Text className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Explain it to me at
                </Text>
                <View className="flex-row flex-wrap gap-2">
                  {EDUCATION_LEVELS.map((option) => {
                    const selected = educationLevel === option.value;
                    return (
                      <Pressable
                        key={option.value}
                        onPress={() => {
                          setEducationLevel(option.value);
                          if (activeDraft) void persistDraftUpdate(activeDraft.id, { educationLevel: option.value });
                        }}
                        accessibilityRole="button"
                        accessibilityState={{ selected }}
                        className={`rounded-full border px-3 py-1.5 ${selected ? "border-primary bg-primary/10" : "border-border bg-background"}`}
                      >
                        <Text className={`text-xs font-medium ${selected ? "text-primary" : "text-muted-foreground"}`}>
                          {option.label}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>
                <Text className="text-xs text-muted-foreground">
                  {EDUCATION_LEVELS.find((option) => option.value === educationLevel)?.blurb}
                </Text>
              </View>

              <Input
                value={content}
                onChangeText={setContent}
                placeholder="Paste your study material here..."
                multiline
                numberOfLines={4}
                editable={!busy}
                style={{ minHeight: 88, textAlignVertical: "top" }}
              />
              {content.length > 0 ? (
                <Text className={`-mt-2 text-right text-xs ${content.trim().length < 10 || content.length > 50_000 ? "text-destructive" : "text-muted-foreground"}`}>
                  {content.length.toLocaleString()} / 50,000 characters
                  {content.trim().length < 10 ? " · Enter at least 10 characters" : ""}
                  {content.length > 50_000 ? " · Text is too long" : ""}
                </Text>
              ) : null}
              <Button
                className="rounded-xl"
                onPress={createAsync}
                disabled={!canCreate}
                loading={busy && uploadPercent == null}
              >
                {busy && uploadPercent == null ? "Creating..." : "Create material"}
              </Button>

              <View className="flex-row gap-2">
                <Button
                  className="min-w-0 flex-1 rounded-lg px-1"
                  size="sm"
                  variant="outline"
                  textClassName="text-[11px]"
                  onPress={pickFile}
                  disabled={busy}
                  icon={<Ionicons name="document-text-outline" size={16} color={tokens.mint} />}
                >
                  Document
                </Button>
                <Button
                  className="min-w-0 flex-1 rounded-lg px-1"
                  size="sm"
                  variant="outline"
                  textClassName="text-[11px]"
                  onPress={pickImagePages}
                  disabled={busy}
                  icon={<Ionicons name="images-outline" size={16} color={tokens.mint} />}
                >
                  Photos
                </Button>
                <Button
                  className="min-w-0 flex-1 rounded-lg px-1"
                  size="sm"
                  variant="outline"
                  textClassName="text-[11px]"
                  onPress={capturePage}
                  disabled={busy}
                  icon={<Ionicons name="camera-outline" size={16} color={tokens.mint} />}
                >
                  Camera
                </Button>
              </View>
              <Text className="text-xs leading-5 text-muted-foreground">
                PDF, DOCX, TXT, Markdown, or photos. PDFs can be previewed and selected page by page.
              </Text>

              {pdfPreviewLoading ? (
                <View className="flex-row items-center gap-2 rounded-xl border border-border bg-background/70 p-3">
                  <PagePaySpinner size={16} />
                  <Text className="text-xs text-muted-foreground">Preparing PDF page previews…</Text>
                </View>
              ) : null}

              {pdfPreviewFile && !pdfPreviewLoading ? (
                <View className="gap-3 rounded-xl border border-border bg-background/70 p-3">
                  <View className="flex-row items-center justify-between gap-2">
                    <View className="min-w-0 flex-1">
                      <Text className="text-sm font-semibold text-foreground" numberOfLines={1}>{pdfPreviewFile.name}</Text>
                      <Text className="text-xs text-muted-foreground">
                        {selectedPdfPages.length} of {pdfPreviewPages.length} pages selected
                      </Text>
                    </View>
                    <View className="flex-row gap-2">
                      <Button size="sm" variant="outline" className="min-h-8 min-w-0 rounded-lg px-2 py-1" textClassName="text-xs" onPress={() => void selectAllPdfPages(true)} disabled={busy}>
                        All
                      </Button>
                      <Button size="sm" variant="outline" className="min-h-8 min-w-0 rounded-lg px-2 py-1" textClassName="text-xs" onPress={() => void selectAllPdfPages(false)} disabled={busy}>
                        None
                      </Button>
                    </View>
                  </View>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="gap-2">
                    {pdfPreviewPages.map((page) => {
                      const selected = selectedPdfPages.includes(page.page);
                      return (
                        <Pressable
                          key={page.page}
                          onPress={() => void togglePdfPage(page.page)}
                          accessibilityRole="checkbox"
                          accessibilityState={{ checked: selected }}
                          accessibilityLabel={`Page ${page.page}${selected ? " selected" : ""}`}
                          className={`w-24 overflow-hidden rounded-lg border ${selected ? "border-primary bg-primary/10" : "border-border bg-background"}`}
                        >
                          <Image source={{ uri: page.uri }} contentFit="contain" style={{ width: 94, height: 128 }} />
                          <View className="flex-row items-center justify-between px-2 py-1">
                            <Text className="text-[10px] font-medium text-foreground">Page {page.page}</Text>
                            <Ionicons name={selected ? "checkbox" : "square-outline"} size={14} color={selected ? tokens.mint : tokens.inkMuted} />
                          </View>
                        </Pressable>
                      );
                    })}
                  </ScrollView>
                  <View className="flex-row gap-2">
                    <Button
                      size="sm"
                      className="min-h-9 min-w-0 flex-1 rounded-lg px-3 py-1"
                      textClassName="text-xs"
                      onPress={() => void uploadDocument(pdfPreviewFile, selectedPdfPages, activeDraft)}
                      disabled={busy || selectedPdfPages.length === 0}
                      icon={busy ? <PagePaySpinner size={15} /> : undefined}
                    >
                      {busy ? "Uploading…" : `Upload ${selectedPdfPages.length} pages`}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="min-h-9 min-w-0 rounded-lg px-3 py-1"
                      textClassName="text-xs"
                      onPress={() => {
                        setPdfPreviewFile(null);
                        setPdfPreviewPages([]);
                        setSelectedPdfPages([]);
                        setActiveDraft(null);
                      }}
                      disabled={busy}
                    >
                      Close
                    </Button>
                  </View>
                </View>
              ) : null}

              {uploadDrafts.length > 0 && !pdfPreviewFile ? (
                <View className="gap-2 rounded-xl border border-border bg-background/70 p-3">
                  <Text className="text-sm font-semibold text-foreground">Saved PDF uploads</Text>
                  {uploadDrafts.map((draft) => (
                    <View key={draft.id} className="flex-row items-center gap-2 rounded-lg border border-border bg-background p-2">
                      <Ionicons name="document-text-outline" size={16} color={tokens.mint} />
                      <View className="min-w-0 flex-1">
                        <Text className="text-xs font-medium text-foreground" numberOfLines={1}>{draft.name}</Text>
                        <Text className="text-[10px] text-muted-foreground">
                          {draft.status === "failed" ? "Retry available" : `${draft.selectedPages.length} pages selected`}
                        </Text>
                      </View>
                      <Button size="sm" className="min-h-8 min-w-0 rounded-md px-2 py-1" textClassName="text-[10px]" onPress={() => resumeDraft(draft)} disabled={busy}>
                        {draft.status === "processing" && draft.jobId ? "Resume" : "Open"}
                      </Button>
                      <Pressable onPress={() => discardDraft(draft)} hitSlop={8} accessibilityLabel={`Discard ${draft.name}`}>
                        <Ionicons name="trash-outline" size={15} color={tokens.inkMuted} />
                      </Pressable>
                    </View>
                  ))}
                </View>
              ) : null}

              {selectedImages.length > 0 ? (
                <View className="gap-3 rounded-xl border border-border bg-background/70 p-3">
                  <View className="flex-row items-center justify-between">
                    <View>
                      <Text className="text-sm font-semibold text-foreground">Scanned pages</Text>
                      <Text className="text-xs text-muted-foreground">{selectedImages.length} photo{selectedImages.length === 1 ? "" : "s"} · OCR creates one material</Text>
                    </View>
                    <Pressable onPress={() => setSelectedImages([])} accessibilityRole="button" accessibilityLabel="Clear selected photos">
                      <Ionicons name="close-circle-outline" size={19} color={tokens.inkMuted} />
                    </Pressable>
                  </View>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="gap-2">
                    {selectedImages.map((file, index) => (
                      <View key={`${file.uri}-${index}`} className="overflow-hidden rounded-lg border border-border">
                        <View>
                          <Image source={{ uri: file.uri }} contentFit="cover" style={{ width: 84, height: 112 }} />
                          <Pressable
                            onPress={() => setSelectedImages((current) => current.filter((_, currentIndex) => currentIndex !== index))}
                            hitSlop={6}
                            accessibilityRole="button"
                            accessibilityLabel={`Remove page ${index + 1}`}
                            className="absolute right-1 top-1 h-6 w-6 items-center justify-center rounded-full bg-background/90"
                          >
                            <Ionicons name="close" size={14} color={tokens.ink} />
                          </Pressable>
                        </View>
                        <Text className="px-2 py-1 text-[10px] text-muted-foreground">Page {index + 1}</Text>
                      </View>
                    ))}
                  </ScrollView>
                  <Button
                    size="sm"
                    className="min-h-9 min-w-0 self-start rounded-lg px-3 py-1"
                    textClassName="text-xs"
                    onPress={() => void uploadImagePages()}
                    disabled={busy}
                    icon={busy ? <PagePaySpinner size={15} /> : <Ionicons name="cloud-upload-outline" size={14} color={tokens.mintText} />}
                  >
                    {busy ? "Uploading…" : "Upload scanned pages"}
                  </Button>
                </View>
              ) : null}

              {busy || job ? (
                <View className="gap-2 rounded-xl border border-border bg-background/70 p-3">
                  <View className="flex-row items-center justify-between">
                    <Text className="text-sm font-medium text-foreground">
                      {job?.status === "failed" ? "Processing failed" : job?.status === "completed" ? "Processing complete" : "Processing material"}
                    </Text>
                    <Text className="text-xs text-muted-foreground">{jobProgress}%</Text>
                  </View>
                  <View className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <View className="h-full rounded-full bg-primary" style={{ width: `${jobProgress}%` }} />
                  </View>
                  <Text className="text-xs text-muted-foreground">
                    {uploadPercent != null && uploadPercent < 100 ? `Uploading file… ${uploadPercent}%` : stageLabel(job?.stage || job?.status)}
                  </Text>
                  {job?.status === "failed" && job.error ? (
                    <Text className="text-xs text-destructive">{job.error}</Text>
                  ) : null}
                </View>
              ) : null}

            </CardContent>
          </Card>

          <View className="flex-row items-end justify-between px-1">
            <View className="gap-1">
              <Text
                className="text-xl font-semibold text-foreground"
                style={{ fontFamily: Fonts.editorialSemiBold as string }}
              >
                Your materials
              </Text>
              <Text className="text-xs text-muted-foreground">Pick up where you left off.</Text>
            </View>
            {q.data ? (
              <Text className="pb-0.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {q.data.length} {q.data.length === 1 ? "material" : "materials"}
              </Text>
            ) : null}
          </View>

          {q.isLoading && !q.data ? (
            <View className="gap-3">
              {[0, 1, 2].map((item) => (
                <Card key={item} className="rounded-2xl p-4">
                  <CardContent className="gap-3 py-0">
                    <Skeleton className="h-5 w-2/3" />
                    <Skeleton className="h-4 w-1/3" />
                  </CardContent>
                </Card>
              ))}
            </View>
          ) : q.error && !q.data ? (
            <Card className="rounded-2xl p-4">
              <CardContent className="gap-3 py-0">
                <Text className="text-sm text-destructive">{(q.error as Error).message}</Text>
                <Button className="rounded-xl" variant="outline" onPress={() => void onRefresh()}>Retry</Button>
              </CardContent>
            </Card>
          ) : (q.data?.length ?? 0) === 0 ? (
            <Card className="rounded-2xl p-5">
              <CardContent className="items-center gap-2 py-5">
                <View className="mb-1 h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
                  <Ionicons name="library-outline" size={27} color={tokens.mint} />
                </View>
                <Text
                  className="text-base font-semibold text-foreground"
                  style={{ fontFamily: Fonts.editorialSemiBold as string }}
                >
                  Your library starts here
                </Text>
                <Text className="max-w-72 text-center text-sm leading-5 text-muted-foreground">
                  Upload a file or paste your notes above to create your first study material.
                </Text>
              </CardContent>
            </Card>
          ) : (
            <View className="gap-3">
              {q.data!.map((m) => (
                <Pressable
                  key={m.id}
                  onPress={() => router.push(`/(app)/study/${m.id}` as any)}
                  style={({ pressed }) => ({ opacity: pressed ? 0.82 : 1, transform: [{ scale: pressed ? 0.99 : 1 }] })}
                  accessibilityRole="button"
                  accessibilityLabel={`Open ${m.title}`}
                  accessibilityHint="Opens this study material"
                >
                  <Card className="rounded-2xl p-4">
                    <CardContent className="gap-3 py-0">
                      <View className="flex-row items-center gap-3">
                        <View className="h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
                          <Ionicons name="book-outline" size={19} color={tokens.mint} />
                        </View>
                        <View className="min-w-0 flex-1 gap-1">
                          <Text className="text-base font-semibold text-foreground" numberOfLines={2}>{m.title}</Text>
                          <Text className="text-xs text-muted-foreground" numberOfLines={1}>
                            {[m.exam_type, formatDate(m.created_at)].filter(Boolean).join(" · ")}
                          </Text>
                        </View>
                        <Pressable
                          onPress={(e) => { e.stopPropagation?.(); confirmDelete(m); }}
                          hitSlop={10}
                          accessibilityRole="button"
                          accessibilityLabel={`Delete ${m.title}`}
                        >
                          <Ionicons name="ellipsis-vertical" size={18} color={tokens.inkMuted} />
                        </Pressable>
                      </View>
                      <View className="flex-row items-center justify-between gap-2 border-t border-border pt-3">
                        <View className="flex-1 flex-row flex-wrap gap-1.5">
                          {m.asset_types.length > 0 ? m.asset_types.map((t) => (
                            <View key={t} className="rounded-full border border-border bg-background px-2.5 py-1">
                              <Text className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{t}</Text>
                            </View>
                          )) : (
                            <Text className="text-xs text-muted-foreground">No study assets yet</Text>
                          )}
                        </View>
                        <Ionicons name="chevron-forward" size={17} color={tokens.inkMuted} />
                      </View>
                    </CardContent>
                  </Card>
                </Pressable>
              ))}
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
