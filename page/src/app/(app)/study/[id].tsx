import { useCallback, useMemo, useState } from "react";
import { Alert, Pressable, RefreshControl, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useLocalSearchParams, useRouter } from "expo-router";
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
import { RichText } from "@/components/study/RichText";
import { SpecialBlockCard, type ContentBlock as StudyContentBlock } from "@/components/study/SpecialBlockCard";
import { Fonts, PagePay } from "@/constants/theme";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";
import { fetchWalletBalance } from "@/src/shared/api/wallet";
import {
  deleteAsset,
  deleteMaterial,
  generateAsset,
  getMaterial,
  submitEssay,
  unlockAsset,
  updateAsset,
  updateMaterial,
  type AssetItem,
  type EssayReviewResponse,
} from "@/src/shared/api/study";

const ASSET_TYPES = ["mcq", "flashcard", "essay"] as const;
const DIFFICULTIES = ["easy", "medium", "hard"] as const;

type JsonObject = Record<string, unknown>;

function asObject(value: unknown): JsonObject | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as JsonObject
    : null;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function previewBlock(value: unknown, index: number, tokens: (typeof PagePay)["light"]) {
  const source = asObject(value);
  if (!source) return null;
  const type = asString(source.type);
  const text = asString(source.text);
  if (type === "heading") {
    return (
      <Text key={index} className="text-base font-semibold text-foreground" style={{ fontFamily: Fonts.editorialSemiBold as string }}>
        {text}
      </Text>
    );
  }
  if (type === "body") {
    return <RichText key={index} color={tokens.inkMuted} fontSize={14} lineHeight={22}>{text}</RichText>;
  }
  if (type === "list" || type === "numbered_list" || type === "recap") {
    return (
      <View key={index} className="gap-1.5">
        {type === "recap" ? <Text className="text-xs font-semibold uppercase tracking-wide text-primary">Key takeaways</Text> : null}
        {asStringList(source.items).slice(0, 3).map((item, itemIndex) => (
          <View key={`${index}-${itemIndex}`} className="flex-row gap-2">
            <Text className="text-sm text-primary">{type === "numbered_list" ? `${itemIndex + 1}.` : "•"}</Text>
            <RichText color={tokens.inkMuted} fontSize={13} lineHeight={20}>{item}</RichText>
          </View>
        ))}
      </View>
    );
  }
  if (type === "figure") {
    return (
      <View key={index} className="gap-1 rounded-xl border border-border bg-background/70 p-3">
        <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {asString(source.caption) || "Figure"}
        </Text>
        {text ? <Text className="text-sm leading-5 text-foreground">{text}</Text> : null}
      </View>
    );
  }
  if (["tip", "warning", "calculation", "code", "quote", "formula", "statement", "definition", "table"].includes(type)) {
    const block: StudyContentBlock = {
      type,
      text,
      label: asString(source.label),
      level: typeof source.level === "number" ? source.level : undefined,
      items: asStringList(source.items),
      steps: asStringList(source.steps),
      language: asString(source.language),
      attribution: asString(source.attribution),
      description: asString(source.description),
      term: asString(source.term),
      headers: asStringList(source.headers),
      rows: Array.isArray(source.rows)
        ? source.rows.map((row) => asStringList(row))
        : [],
    };
    return <SpecialBlockCard key={index} block={block} tokens={tokens} index={index} />;
  }
  return text ? <RichText key={index} color={tokens.inkMuted} fontSize={14} lineHeight={22}>{text}</RichText> : null;
}

function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      className={`rounded-full border px-3 py-1.5 ${selected ? "border-primary bg-primary/10" : "border-border bg-background"}`}
    >
      <Text className={`text-xs font-medium ${selected ? "text-primary" : "text-muted-foreground"}`}>{label}</Text>
    </Pressable>
  );
}

function AssetContent({ asset }: { asset: AssetItem }) {
  const c = asset.content;
  if (!c) return <Text className="text-sm text-muted-foreground">No content.</Text>;

  if (asset.asset_type === "mcq" && Array.isArray(c.questions)) {
    return (
      <View className="gap-3">
        {c.questions.map((q: any, i: number) => (
          <View key={i} className="gap-1.5 rounded-xl border border-border bg-background p-3">
            <Text className="text-sm font-semibold text-foreground">{i + 1}. {q.question}</Text>
            {Array.isArray(q.options) ? q.options.map((opt: string, oi: number) => {
              const correct = q.correct_index === oi;
              return (
                <Text key={oi} className={`text-sm ${correct ? "font-semibold text-green-600" : "text-foreground"}`}>
                  {String.fromCharCode(65 + oi)}. {opt}{correct ? " ✓" : ""}
                </Text>
              );
            }) : null}
            {q.explanation ? <Text className="text-xs text-muted-foreground mt-1">{q.explanation}</Text> : null}
          </View>
        ))}
      </View>
    );
  }

  if (asset.asset_type === "flashcard" && Array.isArray(c.flashcards)) {
    return (
      <View className="gap-3">
        {c.flashcards.map((f: any, i: number) => (
          <View key={i} className="gap-1 rounded-xl border border-border bg-background p-3">
            <Text className="text-xs font-semibold text-muted-foreground uppercase">Front</Text>
            <Text className="text-sm text-foreground">{f.front}</Text>
            <Text className="text-xs font-semibold text-muted-foreground uppercase mt-1">Back</Text>
            <Text className="text-sm text-foreground">{f.back}</Text>
          </View>
        ))}
      </View>
    );
  }

  if (asset.asset_type === "essay" && Array.isArray(c.essays)) {
    return (
      <View className="gap-3">
        {c.essays.map((e: any, i: number) => (
          <View key={i} className="gap-1.5 rounded-xl border border-border bg-background p-3">
            <Text className="text-sm font-semibold text-foreground">Q{i + 1}. {e.prompt}</Text>
            {Array.isArray(e.key_points) && e.key_points.length ? (
              <View className="gap-0.5">
                <Text className="text-xs font-semibold text-muted-foreground">Key points</Text>
                {e.key_points.map((kp: string, ki: number) => (
                  <Text key={ki} className="text-xs text-foreground">• {kp}</Text>
                ))}
              </View>
            ) : null}
            {e.sample_answer ? (
              <View className="gap-0.5">
                <Text className="text-xs font-semibold text-muted-foreground">Sample answer</Text>
                <Text className="text-xs text-foreground">{e.sample_answer}</Text>
              </View>
            ) : null}
          </View>
        ))}
      </View>
    );
  }

  return <Text className="text-xs text-muted-foreground">{JSON.stringify(c, null, 2)}</Text>;
}

export default function StudyMaterialDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const materialId = Number(id);
  const isValidMaterialId = Number.isSafeInteger(materialId) && materialId > 0;
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [refreshing, setRefreshing] = useState(false);

  // generate form
  const [genType, setGenType] = useState<(typeof ASSET_TYPES)[number]>("mcq");
  const [genCount, setGenCount] = useState("5");
  const [genTopic, setGenTopic] = useState("");
  const [genDifficulty, setGenDifficulty] = useState<(typeof DIFFICULTIES)[number]>("medium");

  // edit material
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editContent, setEditContent] = useState("");
  const [editExamType, setEditExamType] = useState("");
  const [editEducationLevel, setEditEducationLevel] = useState("");

  // edit asset topic
  const [editingAssetId, setEditingAssetId] = useState<number | null>(null);
  const [editAssetTopic, setEditAssetTopic] = useState("");

  // essay submit
  const [essayText, setEssayText] = useState("");
  const [essayAssetId, setEssayAssetId] = useState<number | null>(null);
  const [essayQuestionIndex, setEssayQuestionIndex] = useState(0);
  const [essayTopic, setEssayTopic] = useState("");
  const [review, setReview] = useState<EssayReviewResponse | null>(null);

  const detailKey = ["study", "material", materialId] as const;
  const q = useQuery({
    queryKey: detailKey,
    queryFn: () => getMaterial(materialId),
    enabled: isValidMaterialId,
  });
  const balanceQ = useQuery({
    queryKey: ["wallet", "balance"],
    queryFn: fetchWalletBalance,
    enabled: isValidMaterialId,
  });

  const onRefresh = useCallback(async () => {
    if (!isValidMaterialId) return;
    setRefreshing(true);
    try {
      await Promise.all([q.refetch(), balanceQ.refetch()]);
    } finally {
      setRefreshing(false);
    }
  }, [isValidMaterialId, q, balanceQ]);

  const genMut = useMutation({
    mutationFn: generateAsset,
    onSuccess: (res) => {
      toast({ title: "Asset generated", description: `${res.asset_type.toUpperCase()} ready to unlock (${res.points_to_unlock} SP).`, variant: "success" });
      setGenTopic("");
      void qc.invalidateQueries({ queryKey: detailKey });
      void qc.invalidateQueries({ queryKey: ["study", "materials"] });
    },
    onError: (e: Error) => toast({ title: "Generate failed", description: e.message, variant: "destructive" }),
  });

  const unlockMut = useMutation({
    mutationFn: unlockAsset,
    onSuccess: (res) => {
      toast({ title: res.method === "already_unlocked" ? "Already unlocked" : "Unlocked", description: res.method === "already_unlocked" ? "Content available." : `Spent ${res.points_spent} SP. Balance: ${res.new_sp_balance} SP.`, variant: "success" });
      void qc.invalidateQueries({ queryKey: detailKey });
      void qc.invalidateQueries({ queryKey: ["wallet", "balance"] });
    },
    onError: (e: Error) => toast({ title: "Unlock failed", description: e.message, variant: "destructive" }),
  });

  const delAssetMut = useMutation({
    mutationFn: deleteAsset,
    onSuccess: () => {
      toast({ title: "Asset deleted", variant: "success" });
      void qc.invalidateQueries({ queryKey: detailKey });
      void qc.invalidateQueries({ queryKey: ["study", "materials"] });
    },
    onError: (e: Error) => toast({ title: "Delete failed", description: e.message, variant: "destructive" }),
  });

  const updateMatMut = useMutation({
    mutationFn: (input: { title?: string; content?: string; exam_type?: string | null; education_level?: string | null }) =>
      updateMaterial(materialId, input),
    onSuccess: () => {
      toast({ title: "Material updated", variant: "success" });
      setEditing(false);
      void qc.invalidateQueries({ queryKey: detailKey });
      void qc.invalidateQueries({ queryKey: ["study", "materials"] });
    },
    onError: (e: Error) => toast({ title: "Update failed", description: e.message, variant: "destructive" }),
  });

  const updateAssetMut = useMutation({
    mutationFn: ({ id, topic }: { id: number; topic: string | null }) => updateAsset(id, { topic }),
    onSuccess: () => {
      toast({ title: "Asset updated", variant: "success" });
      setEditingAssetId(null);
      setEditAssetTopic("");
      void qc.invalidateQueries({ queryKey: detailKey });
      void qc.invalidateQueries({ queryKey: ["study", "materials"] });
    },
    onError: (e: Error) => toast({ title: "Update failed", description: e.message, variant: "destructive" }),
  });

  const deleteMatMut = useMutation({
    mutationFn: () => deleteMaterial(materialId),
    onSuccess: () => {
      toast({ title: "Material deleted", variant: "success" });
      void qc.invalidateQueries({ queryKey: ["study", "materials"] });
      router.replace("/(app)/study" as any);
    },
    onError: (e: Error) => toast({ title: "Delete failed", description: e.message, variant: "destructive" }),
  });

  const essayMut = useMutation({
    mutationFn: submitEssay,
    onSuccess: (res) => {
      setReview(res);
      toast({ title: "Essay reviewed", description: res.score != null ? `Score: ${res.score}` : undefined, variant: "success" });
    },
    onError: (e: Error) => toast({ title: "Review failed", description: e.message, variant: "destructive" }),
  });

  const material = q.data;
  const essayAssets = useMemo(() => (material?.assets || []).filter((a) => a.asset_type === "essay"), [material]);
  const selectedEssayAsset = essayAssets.find((a) => a.id === essayAssetId) || null;
  const essayQuestionCount = useMemo(() => {
    if (!selectedEssayAsset?.content?.essays) return 0;
    return Array.isArray(selectedEssayAsset.content.essays) ? selectedEssayAsset.content.essays.length : 0;
  }, [selectedEssayAsset]);

  const startEdit = () => {
    if (!material) return;
    setEditTitle(material.title);
    setEditContent(material.content || "");
    setEditExamType(material.exam_type || "");
    setEditEducationLevel(material.education_level || "");
    setEditing(true);
  };

  const confirmDeleteMaterial = () => {
    Alert.alert("Delete material?", "Delete this material and all its assets/unlocks? This cannot be undone.", [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => deleteMatMut.mutate() },
    ]);
  };

  const confirmDeleteAsset = (a: AssetItem) => {
    Alert.alert("Delete asset?", `Delete this ${a.asset_type} asset? Unlock records will be removed (no SP refund).`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => delAssetMut.mutate(a.id) },
    ]);
  };

  const sp = balanceQ.data?.service_points_sp ?? 0;
  const countNum = Math.max(1, Math.min(20, parseInt(genCount || "5", 10) || 5));
  const explanationStructure = asObject(material?.explanation_structure);
  const explanationBlocks = Array.isArray(explanationStructure?.content_blocks)
    ? explanationStructure.content_blocks
    : [];

  return (
    <View className="flex-1 bg-background" style={{ backgroundColor: tokens.paper }}>
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title={material?.title || "Material"} showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView
          className="flex-1"
          contentContainerClassName="gap-5 px-4 py-5 pb-10"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={tokens.mint} />}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {!isValidMaterialId ? (
            <Card className="rounded-2xl p-4">
              <CardContent className="items-center gap-3 py-2">
                <View className="h-12 w-12 items-center justify-center rounded-full bg-destructive/10">
                  <Ionicons name="alert-circle-outline" size={24} color={tokens.signal} />
                </View>
                <Text className="text-center text-sm text-muted-foreground">
                  This study material link is invalid.
                </Text>
                <Button
                  className="min-h-10 min-w-0 rounded-lg px-4 py-1.5"
                  size="sm"
                  textClassName="text-sm"
                  onPress={() => router.replace("/(app)/study" as any)}
                >
                  Back to study
                </Button>
              </CardContent>
            </Card>
          ) : q.isLoading && !material ? (
            <Card className="rounded-2xl p-4"><CardContent className="gap-3 py-0"><Skeleton className="h-6 w-48" /><Skeleton className="h-24 w-full" /></CardContent></Card>
          ) : q.error ? (
            <Card className="rounded-2xl p-4"><CardContent className="gap-3 py-0">
              <Text className="text-sm text-destructive">{(q.error as Error).message}</Text>
              <Button
                className="min-h-10 min-w-0 self-start rounded-lg px-4 py-1.5"
                size="sm"
                textClassName="text-sm"
                variant="outline"
                onPress={() => void onRefresh()}
              >
                Retry
              </Button>
            </CardContent></Card>
          ) : material ? (
            <>
              <Card className="rounded-2xl p-4">
                <CardContent className="gap-4 py-0">
                  <View className="flex-row items-start gap-3">
                    <View className="h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                      <Ionicons name="book-outline" size={21} color={tokens.mint} />
                    </View>
                    <View className="min-w-0 flex-1 gap-1">
                      <Text className="text-xs font-semibold uppercase tracking-widest text-primary">Study material</Text>
                      <Text
                        className="text-xl font-semibold leading-7 text-foreground"
                        style={{ fontFamily: Fonts.editorialSemiBold as string }}
                      >
                        {material.title}
                      </Text>
                      <Text className="text-xs text-muted-foreground">
                        {[material.exam_type, material.education_level].filter(Boolean).join(" · ") || "Your learning resource"}
                      </Text>
                    </View>
                    <View className="flex-row gap-2">
                      <Pressable
                        onPress={startEdit}
                        hitSlop={8}
                        className="h-9 w-9 items-center justify-center rounded-full border border-border bg-background"
                        accessibilityRole="button"
                        accessibilityLabel="Edit material"
                      >
                        <Ionicons name="create-outline" size={17} color={tokens.ink} />
                      </Pressable>
                      <Pressable
                        onPress={confirmDeleteMaterial}
                        hitSlop={8}
                        className="h-9 w-9 items-center justify-center rounded-full border border-border bg-background"
                        accessibilityRole="button"
                        accessibilityLabel="Delete material"
                      >
                        <Ionicons name="trash-outline" size={17} color={tokens.inkMuted} />
                      </Pressable>
                    </View>
                  </View>
                  {editing ? (
                    <View className="gap-3 rounded-xl border border-border bg-background/70 p-3">
                      <Label>Title</Label>
                      <Input value={editTitle} onChangeText={setEditTitle} />
                      <Label>Content</Label>
                      <Input value={editContent} onChangeText={setEditContent} multiline style={{ minHeight: 120, textAlignVertical: "top" }} />
                      <View className="flex-row gap-2">
                        <View className="flex-1 gap-1.5">
                          <Label>Exam type</Label>
                          <Input value={editExamType} onChangeText={setEditExamType} placeholder="JAMB, WAEC..." />
                        </View>
                        <View className="flex-1 gap-1.5">
                          <Label>Level</Label>
                          <Input value={editEducationLevel} onChangeText={setEditEducationLevel} placeholder="secondary..." />
                        </View>
                      </View>
                      <View className="flex-row gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onPress={() => setEditing(false)}
                          className="min-h-10 min-w-0 flex-1 rounded-lg px-3 py-1.5"
                          textClassName="text-sm"
                        >
                          Cancel
                        </Button>
                        <Button
                          size="sm"
                          className="min-h-10 min-w-0 flex-1 rounded-lg px-3 py-1.5"
                          textClassName="text-sm"
                          onPress={() => {
                            const payload: any = {};
                            if (editTitle.trim() !== (material.title || "")) payload.title = editTitle.trim() || undefined;
                            if (editContent.trim() !== (material.content || "")) payload.content = editContent.trim() || undefined;
                            if (editExamType.trim() !== (material.exam_type || "")) payload.exam_type = editExamType.trim() || null;
                            if (editEducationLevel.trim() !== (material.education_level || "")) payload.education_level = editEducationLevel.trim() || null;
                            if (Object.keys(payload).length === 0) {
                              setEditing(false);
                              return;
                            }
                            updateMatMut.mutate(payload);
                          }}
                          disabled={updateMatMut.isPending}
                          icon={updateMatMut.isPending ? <PagePaySpinner size={16} /> : undefined}
                        >
                          Save
                        </Button>
                      </View>
                    </View>
                  ) : (
                    <View className="gap-2 rounded-xl border border-border bg-background/70 p-3">
                      <View className="flex-row items-center gap-2">
                        <Ionicons name="reader-outline" size={16} color={tokens.mint} />
                        <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Material overview</Text>
                      </View>
                      {explanationBlocks.length ? (
                        <View className="gap-3">
                          {explanationBlocks.slice(0, 3).map((block, index) => previewBlock(block, index, tokens))}
                          {explanationBlocks.length > 3 ? (
                            <Text className="text-xs text-muted-foreground">Open the reader to see the complete formatted material.</Text>
                          ) : null}
                        </View>
                      ) : (
                        <Text className="text-sm leading-6 text-destructive">
                          The server returned no formatted explanation for this material.
                        </Text>
                      )}
                      <View className="flex-row gap-2 pt-1">
                        <Button
                          size="sm"
                          className="min-h-9 min-w-0 flex-1 rounded-lg px-3 py-1"
                          textClassName="text-xs"
                          onPress={() => router.push(`/(app)/study/${materialId}/reader` as never)}
                          icon={<Ionicons name="school-outline" size={14} color={tokens.mintText} />}
                        >
                          Read material
                        </Button>
                        {material.has_original_file ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="min-h-9 min-w-0 flex-1 rounded-lg px-3 py-1"
                            textClassName="text-xs"
                            onPress={() => router.push(`/(app)/study/${materialId}/file-viewer` as never)}
                            icon={<Ionicons name="document-text-outline" size={14} color={tokens.mint} />}
                          >
                            Original pages
                          </Button>
                        ) : null}
                      </View>
                    </View>
                  )}
                </CardContent>
              </Card>

              <Card className="rounded-2xl p-4">
                <CardContent className="gap-4 py-0">
                  <View className="flex-row items-center justify-between">
                    <View className="gap-1">
                      <Text
                        className="text-lg font-semibold text-foreground"
                        style={{ fontFamily: Fonts.editorialSemiBold as string }}
                      >
                        Build study assets
                      </Text>
                      <Text className="text-xs text-muted-foreground">Create practice material from this upload.</Text>
                    </View>
                    <View className="flex-row items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1.5">
                      <Ionicons name="wallet-outline" size={14} color={tokens.mint} />
                      <Text className="text-xs font-semibold text-foreground">{sp} SP</Text>
                    </View>
                  </View>
                  <View className="gap-2">
                    <Label>Type</Label>
                    <View className="flex-row flex-wrap gap-2">
                      {ASSET_TYPES.map((t) => (
                        <Chip key={t} label={t.toUpperCase()} selected={genType === t} onPress={() => setGenType(t)} />
                      ))}
                    </View>
                  </View>
                  <View className="flex-row gap-2">
                    <View className="flex-1 gap-1.5">
                      <Label>Count (1-20)</Label>
                      <Input value={genCount} onChangeText={setGenCount} keyboardType="number-pad" />
                    </View>
                    <View className="flex-1 gap-1.5">
                      <Label>Difficulty</Label>
                      <View className="flex-row flex-wrap gap-1.5">
                        {DIFFICULTIES.map((d) => (
                          <Chip key={d} label={d} selected={genDifficulty === d} onPress={() => setGenDifficulty(d)} />
                        ))}
                      </View>
                    </View>
                  </View>
                  <View className="gap-1.5">
                    <Label>Topic (optional)</Label>
                    <Input value={genTopic} onChangeText={setGenTopic} placeholder="Focus topic..." />
                  </View>
                  <Button
                    className="min-h-10 min-w-0 self-start rounded-lg px-4 py-1.5"
                    size="sm"
                    textClassName="text-sm"
                    onPress={() => genMut.mutate({ material_id: materialId, asset_type: genType, count: countNum, topic: genTopic.trim() || null, difficulty: genDifficulty })}
                    disabled={genMut.isPending}
                    icon={genMut.isPending ? <PagePaySpinner size={16} /> : undefined}
                  >
                    {genMut.isPending ? "Generating..." : "Generate"}
                  </Button>
                </CardContent>
              </Card>

              <Card className="rounded-2xl p-4">
                <CardContent className="gap-4 py-0">
                  <View className="flex-row items-end justify-between">
                    <View className="gap-1">
                      <Text
                        className="text-lg font-semibold text-foreground"
                        style={{ fontFamily: Fonts.editorialSemiBold as string }}
                      >
                        Your study assets
                      </Text>
                      <Text className="text-xs text-muted-foreground">Generated for this material.</Text>
                    </View>
                    <Text className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {material.assets.length} {material.assets.length === 1 ? "asset" : "assets"}
                    </Text>
                  </View>
                  {material.assets.length === 0 ? (
                    <View className="items-center gap-2 rounded-xl border border-dashed border-border bg-background/70 px-4 py-6">
                      <Ionicons name="layers-outline" size={24} color={tokens.inkMuted} />
                      <Text className="text-center text-sm text-muted-foreground">
                        No assets yet. Generate your first practice set above.
                      </Text>
                    </View>
                  ) : (
                    <View className="gap-3">
                      {material.assets.map((a) => (
                        <View key={a.id} className="gap-3 rounded-xl border border-border bg-background/70 p-3">
                          <View className="flex-row items-center justify-between">
                            <View className="flex-1 flex-row items-center gap-3">
                              <View className="h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                                <Ionicons
                                  name={a.asset_type === "mcq" ? "list-outline" : a.asset_type === "flashcard" ? "albums-outline" : "create-outline"}
                                  size={18}
                                  color={tokens.mint}
                                />
                              </View>
                              <View className="flex-1 gap-1">
                                <Text className="text-sm font-semibold text-foreground uppercase">{a.asset_type}{a.topic ? ` · ${a.topic}` : ""}</Text>
                                <Text className="text-xs text-muted-foreground">
                                  {a.unlocked ? "Ready to study" : `Locked · ${a.points_to_unlock} SP`}
                                </Text>
                              </View>
                            </View>
                            <View className="flex-row items-center gap-2">
                              {!a.unlocked ? (
                                <Button
                                  className="min-h-10 min-w-0 rounded-lg px-3 py-1.5"
                                  size="sm"
                                  textClassName="text-sm"
                                  onPress={() => unlockMut.mutate(a.id)}
                                  disabled={unlockMut.isPending}
                                  icon={unlockMut.isPending ? <PagePaySpinner size={16} /> : undefined}
                                >
                                  Unlock
                                </Button>
                              ) : null}
                              <Pressable
                                onPress={() => {
                                  setEditingAssetId(a.id);
                                  setEditAssetTopic(a.topic || "");
                                }}
                                hitSlop={8}
                                accessibilityRole="button"
                                accessibilityLabel={`Edit ${a.asset_type} topic`}
                              >
                                <Ionicons name="create-outline" size={18} color={tokens.inkMuted} />
                              </Pressable>
                              <Pressable onPress={() => confirmDeleteAsset(a)} hitSlop={8}>
                                <Ionicons name="trash-outline" size={18} color={tokens.inkMuted} />
                              </Pressable>
                            </View>
                          </View>
                          {editingAssetId === a.id ? (
                            <View className="gap-2 rounded-lg border border-border bg-background p-3">
                              <Label>Asset topic</Label>
                              <Input
                                value={editAssetTopic}
                                onChangeText={setEditAssetTopic}
                                placeholder="Optional topic"
                                editable={!updateAssetMut.isPending}
                              />
                              <View className="flex-row gap-2">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="min-h-10 min-w-0 rounded-lg px-3 py-1.5"
                                  textClassName="text-sm"
                                  onPress={() => {
                                    setEditingAssetId(null);
                                    setEditAssetTopic("");
                                  }}
                                  disabled={updateAssetMut.isPending}
                                >
                                  Cancel
                                </Button>
                                <Button
                                  size="sm"
                                  className="min-h-10 min-w-0 rounded-lg px-3 py-1.5"
                                  textClassName="text-sm"
                                  onPress={() => updateAssetMut.mutate({
                                    id: a.id,
                                    topic: editAssetTopic.trim() || null,
                                  })}
                                  disabled={updateAssetMut.isPending}
                                  icon={updateAssetMut.isPending ? <PagePaySpinner size={16} /> : undefined}
                                >
                                  Save topic
                                </Button>
                              </View>
                            </View>
                          ) : a.unlocked ? <AssetContent asset={a} /> : (
                            <Text className="text-xs text-muted-foreground">Unlock to view generated content.</Text>
                          )}
                        </View>
                      ))}
                    </View>
                  )}
                </CardContent>
              </Card>

              <Card className="rounded-2xl p-4">
                <CardContent className="gap-4 py-0">
                  <View className="flex-row items-start gap-3">
                    <View className="h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                      <Ionicons name="create-outline" size={19} color={tokens.mint} />
                    </View>
                    <View className="flex-1 gap-1">
                      <Text
                        className="text-lg font-semibold text-foreground"
                        style={{ fontFamily: Fonts.editorialSemiBold as string }}
                      >
                        Essay review
                      </Text>
                      <Text className="text-xs leading-5 text-muted-foreground">
                        Get feedback on your writing, with the option to target a generated question.
                      </Text>
                    </View>
                  </View>
                  <View className="gap-2">
                    <Label>Target essay asset (optional)</Label>
                    <View className="flex-row flex-wrap gap-2">
                      <Chip label="Generic" selected={essayAssetId == null} onPress={() => { setEssayAssetId(null); setEssayQuestionIndex(0); }} />
                      {essayAssets.map((a) => (
                        <Chip
                          key={a.id}
                          label={`#${a.id}${a.topic ? ` ${a.topic}` : ""}${!a.unlocked ? " (locked)" : ""}`}
                          selected={essayAssetId === a.id}
                          onPress={() => { setEssayAssetId(a.id); setEssayQuestionIndex(0); }}
                        />
                      ))}
                    </View>
                    {selectedEssayAsset && !selectedEssayAsset.unlocked ? (
                      <Text className="text-xs text-amber-600">This essay asset is locked (viewing content requires SP unlock), but you can still target its questions for review.</Text>
                    ) : null}
                    {selectedEssayAsset && essayQuestionCount > 0 ? (
                      <View className="gap-1.5">
                        <Label>Question index (0-{essayQuestionCount - 1})</Label>
                        <View className="flex-row flex-wrap gap-2">
                          {Array.from({ length: essayQuestionCount }).map((_, i) => (
                            <Chip key={i} label={`Q${i + 1}`} selected={essayQuestionIndex === i} onPress={() => setEssayQuestionIndex(i)} />
                          ))}
                        </View>
                      </View>
                    ) : selectedEssayAsset ? (
                      <Text className="text-xs text-muted-foreground">Question details unavailable in list; backend will validate question_index on submit (default 0).</Text>
                    ) : null}
                  </View>
                  <View className="gap-1.5">
                    <Label>Topic (optional, for generic review)</Label>
                    <Input value={essayTopic} onChangeText={setEssayTopic} placeholder="Essay topic" />
                  </View>
                  <View className="gap-1.5">
                    <Label>Your essay</Label>
                    <Input value={essayText} onChangeText={setEssayText} multiline placeholder="Write your essay (min 10 chars)..." style={{ minHeight: 140, textAlignVertical: "top" }} />
                  </View>
                  <Button
                    className="min-h-10 min-w-0 self-start rounded-lg px-4 py-1.5"
                    size="sm"
                    textClassName="text-sm"
                    onPress={() => {
                      setReview(null);
                      const useAsset = selectedEssayAsset ? selectedEssayAsset.id : undefined;
                      essayMut.mutate({
                        material_id: materialId,
                        essay: essayText.trim(),
                        topic: essayTopic.trim() || null,
                        asset_id: useAsset ?? null,
                        question_index: useAsset ? essayQuestionIndex : 0,
                      });
                    }}
                    disabled={essayMut.isPending || essayText.trim().length < 10}
                    icon={essayMut.isPending ? <PagePaySpinner size={16} /> : undefined}
                  >
                    {essayMut.isPending ? "Reviewing..." : "Submit for review"}
                  </Button>
                    {review ? (
                    <View className="gap-2 rounded-xl border border-border bg-background/70 p-3">
                      <Text className="text-sm font-semibold text-foreground">
                        Result: {review.correct ? "Correct" : "Needs work"}{review.score != null ? ` · ${review.score}/100` : ""}
                      </Text>
                      <Text className="text-sm text-foreground">{review.feedback}</Text>
                      {review.suggestions?.length ? (
                        <View className="gap-1">
                          <Text className="text-xs font-semibold text-muted-foreground">Suggestions</Text>
                          {review.suggestions.map((s, i) => <Text key={i} className="text-xs text-foreground">• {s}</Text>)}
                        </View>
                      ) : null}
                    </View>
                  ) : null}
                </CardContent>
              </Card>
            </>
          ) : null}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
