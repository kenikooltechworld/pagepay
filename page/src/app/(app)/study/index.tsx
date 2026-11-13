import { useCallback, useState } from "react";
import { Alert, Pressable, RefreshControl, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import * as DocumentPicker from "expo-document-picker";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import {
  deleteMaterial,
  listMaterials,
  pollSowJob,
  uploadSowDocument,
  uploadSowText,
  type MaterialSummary,
  type SowJobStatus,
} from "@/src/shared/api/study";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

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
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [examType, setExamType] = useState("");
  const [educationLevel, setEducationLevel] = useState("");
  // file upload meta
  const [fileTitle, setFileTitle] = useState("");
  const [fileExamType, setFileExamType] = useState("");
  const [fileEducationLevel, setFileEducationLevel] = useState("");
  const [job, setJob] = useState<SowJobStatus | null>(null);
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  const q = useQuery({ queryKey: ["study", "materials"], queryFn: listMaterials });

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
    if (final.material_id) {
      router.push(`/(app)/study/${final.material_id}` as any);
    }
  };

  const createAsync = async () => {
    if (title.trim().length === 0 || content.trim().length === 0 || busy) return;
    setBusy(true);
    setUploadPercent(null);
    setJob({ job_id: "", status: "queued", progress: 0, stage: "queued" });
    try {
      const accepted = await uploadSowText({
        text: content.trim(),
        exam_type: examType.trim() || null,
        education_level: educationLevel.trim() || null,
      });
      setJob({ job_id: accepted.job_id, status: accepted.status, progress: 5, stage: "queued" });
      // apply provided title hint by updating after? backend may infer title; keep simple
      await runJob(accepted.job_id, "Material created");
      setTitle(""); setContent(""); setExamType(""); setEducationLevel(""); setShowCreate(false);
    } catch (e: any) {
      toast({ title: "Create failed", description: e?.message || "Failed", variant: "destructive" });
      setJob((j) => j ? { ...j, status: "failed", error: e?.message || "Failed" } : j);
    } finally {
      setBusy(false);
      setUploadPercent(null);
    }
  };

  const pickFile = async () => {
    if (busy) return;
    const res = await DocumentPicker.getDocumentAsync({
      type: ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown", "*/*"],
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (res.canceled || !res.assets?.[0]) return;
    const a = res.assets[0];
    setBusy(true);
    setUploadPercent(0);
    setJob({ job_id: "", status: "queued", progress: 0, stage: "queued" });
    try {
      const accepted = await uploadSowDocument({
        file: { uri: a.uri, name: a.name || "material", type: a.mimeType || undefined },
        title: fileTitle.trim() || undefined,
        exam_type: fileExamType.trim() || undefined,
        education_level: fileEducationLevel.trim() || undefined,
        onProgress: (loaded, total) => {
          if (total > 0) setUploadPercent(Math.round((loaded / total) * 100));
        },
      });
      setUploadPercent(100);
      setJob({ job_id: accepted.job_id, status: accepted.status, progress: 10, stage: "queued" });
      await runJob(accepted.job_id, "Material uploaded");
      setFileTitle(""); setFileExamType(""); setFileEducationLevel("");
    } catch (e: any) {
      toast({ title: "Upload failed", description: e?.message || "Failed", variant: "destructive" });
      setJob((j) => j ? { ...j, status: "failed", error: e?.message || "Failed" } : j);
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = (m: MaterialSummary) => {
    Alert.alert("Delete material?", `Delete "${m.title}" and all its assets/unlocks? This cannot be undone.`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => deleteMut.mutate(m.id) },
    ]);
  };

  const canCreate = title.trim().length > 0 && content.trim().length > 0 && !busy;
  const jobProgress = job?.status === "failed" ? 100 : Math.max(0, Math.min(100, job?.progress ?? (busy ? 5 : 0)));

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Study" tokens={tokens} />
        <ScrollView
          className="flex-1"
          contentContainerClassName="px-4 py-4 gap-4 pb-10"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={tokens.mint} />}
          showsVerticalScrollIndicator={false}
        >
          <Card>
            <CardContent className="gap-3 pt-2">
              <View className="flex-row items-center justify-between">
                <Text className="text-base font-semibold text-foreground">Your materials</Text>
                <View className="flex-row gap-2">
                  <Button size="sm" variant="outline" onPress={pickFile} disabled={busy} icon={busy && uploadPercent != null ? <PagePaySpinner size={16} /> : <Ionicons name="cloud-upload-outline" size={16} />}>
                    Upload
                  </Button>
                  <Button size="sm" onPress={() => setShowCreate((v) => !v)} icon={<Ionicons name={showCreate ? "close" : "add"} size={16} color={tokens.mintText} />}>
                    {showCreate ? "Close" : "New"}
                  </Button>
                </View>
              </View>
              <Text className="text-xs text-muted-foreground">Upload a file (PDF/DOCX/TXT/MD) or paste text. Processing runs asynchronously and parses structure when available.</Text>

              {busy || job ? (
                <View className="gap-2 rounded-xl border border-border p-3 mt-1">
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

              <View className="gap-2 rounded-xl border border-border p-3 mt-1">
                <Text className="text-sm font-medium text-foreground">File upload options (optional)</Text>
                <View className="gap-1.5">
                  <Label>Title override</Label>
                  <Input value={fileTitle} onChangeText={setFileTitle} placeholder="Defaults to file name" editable={!busy} />
                </View>
                <View className="flex-row gap-2">
                  <View className="flex-1 gap-1.5">
                    <Label>Exam type</Label>
                    <Input value={fileExamType} onChangeText={setFileExamType} placeholder="JAMB, WAEC..." editable={!busy} />
                  </View>
                  <View className="flex-1 gap-1.5">
                    <Label>Level</Label>
                    <Input value={fileEducationLevel} onChangeText={setFileEducationLevel} placeholder="secondary..." editable={!busy} />
                  </View>
                </View>
                <Text className="text-[11px] text-muted-foreground">Tap Upload to pick a file (PDF/DOCX/TXT/MD, max 10 MB). Progress and parsing status show above.</Text>
              </View>

              {showCreate ? (
                <View className="gap-3 rounded-xl border border-border p-3 mt-1">
                  <View className="gap-1.5">
                    <Label>Title (optional hint)</Label>
                    <Input value={title} onChangeText={setTitle} placeholder="e.g. Biology Week 1" editable={!busy} />
                  </View>
                  <View className="gap-1.5">
                    <Label>Content</Label>
                    <Input
                      value={content}
                      onChangeText={setContent}
                      placeholder="Paste study material text..."
                      multiline
                      numberOfLines={6}
                      editable={!busy}
                      style={{ minHeight: 120, textAlignVertical: "top" }}
                    />
                  </View>
                  <View className="flex-row gap-2">
                    <View className="flex-1 gap-1.5">
                      <Label>Exam type (optional)</Label>
                      <Input value={examType} onChangeText={setExamType} placeholder="JAMB, WAEC..." editable={!busy} />
                    </View>
                    <View className="flex-1 gap-1.5">
                      <Label>Level (optional)</Label>
                      <Input value={educationLevel} onChangeText={setEducationLevel} placeholder="secondary..." editable={!busy} />
                    </View>
                  </View>
                  <Button
                    onPress={createAsync}
                    disabled={!canCreate}
                    icon={busy && uploadPercent == null ? <PagePaySpinner size={20} /> : undefined}
                  >
                    {busy && uploadPercent == null ? "Creating..." : "Create material"}
                  </Button>
                </View>
              ) : null}
            </CardContent>
          </Card>

          {q.isLoading && !q.data ? (
            <Card><CardContent className="gap-3 pt-2"><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></CardContent></Card>
          ) : q.error && !q.data ? (
            <Card><CardContent className="gap-3 pt-2">
              <Text className="text-sm text-destructive">{(q.error as Error).message}</Text>
              <Button variant="outline" onPress={() => void onRefresh()}>Retry</Button>
            </CardContent></Card>
          ) : (q.data?.length ?? 0) === 0 ? (
            <Card><CardContent className="items-center gap-2 py-8">
              <Ionicons name="book-outline" size={36} color={tokens.inkMuted} />
              <Text className="text-sm text-muted-foreground text-center">No study materials yet. Create or upload one to get started.</Text>
            </CardContent></Card>
          ) : (
            <View className="gap-3">
              {q.data!.map((m) => (
                <Pressable key={m.id} onPress={() => router.push(`/(app)/study/${m.id}` as any)} style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}>
                  <Card>
                    <CardContent className="gap-2 pt-2">
                      <View className="flex-row items-start justify-between gap-2">
                        <View className="flex-1 gap-1">
                          <Text className="text-base font-semibold text-foreground" numberOfLines={2}>{m.title}</Text>
                          <Text className="text-xs text-muted-foreground">
                            {m.exam_type ? `${m.exam_type} · ` : ""}{formatDate(m.created_at)}
                          </Text>
                        </View>
                        <Pressable
                          onPress={(e) => { e.stopPropagation?.(); confirmDelete(m); }}
                          hitSlop={8}
                          accessibilityRole="button"
                          accessibilityLabel="Delete material"
                        >
                          <Ionicons name="trash-outline" size={18} color={tokens.inkMuted} />
                        </Pressable>
                      </View>
                      <View className="flex-row flex-wrap gap-1.5">
                        {m.asset_types.length > 0 ? m.asset_types.map((t) => (
                          <View key={t} className="rounded-full border border-border px-2 py-0.5">
                            <Text className="text-[11px] text-muted-foreground uppercase">{t}</Text>
                          </View>
                        )) : <Text className="text-xs text-muted-foreground">No assets yet</Text>}
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
