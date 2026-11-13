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
import { createMaterial, deleteMaterial, listMaterials, uploadMaterialFile, type MaterialSummary } from "@/src/shared/api/study";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
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

  const q = useQuery({ queryKey: ["study", "materials"], queryFn: listMaterials });

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await q.refetch();
    } finally {
      setRefreshing(false);
    }
  }, [q]);

  const createMut = useMutation({
    mutationFn: createMaterial,
    onSuccess: (m) => {
      toast({ title: "Material created", variant: "success" });
      setTitle(""); setContent(""); setExamType(""); setEducationLevel(""); setShowCreate(false);
      void qc.invalidateQueries({ queryKey: ["study", "materials"] });
      router.push(`/(app)/study/${m.id}` as any);
    },
    onError: (e: Error) => toast({ title: "Create failed", description: e.message, variant: "destructive" }),
  });

  const uploadMut = useMutation({
    mutationFn: uploadMaterialFile,
    onSuccess: (m) => {
      toast({ title: "Material uploaded", variant: "success" });
      setFileTitle(""); setFileExamType(""); setFileEducationLevel("");
      void qc.invalidateQueries({ queryKey: ["study", "materials"] });
      router.push(`/(app)/study/${m.id}` as any);
    },
    onError: (e: Error) => toast({ title: "Upload failed", description: e.message, variant: "destructive" }),
  });

  const deleteMut = useMutation({
    mutationFn: deleteMaterial,
    onSuccess: () => {
      toast({ title: "Material deleted", variant: "success" });
      void qc.invalidateQueries({ queryKey: ["study", "materials"] });
    },
    onError: (e: Error) => toast({ title: "Delete failed", description: e.message, variant: "destructive" }),
  });

  const pickFile = async () => {
    const res = await DocumentPicker.getDocumentAsync({
      type: ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown", "*/*"],
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (res.canceled || !res.assets?.[0]) return;
    const a = res.assets[0];
    uploadMut.mutate({
      file: { uri: a.uri, name: a.name || "material", type: a.mimeType || undefined },
      title: fileTitle.trim() || undefined,
      exam_type: fileExamType.trim() || undefined,
      education_level: fileEducationLevel.trim() || undefined,
    });
  };

  const confirmDelete = (m: MaterialSummary) => {
    Alert.alert("Delete material?", `Delete "${m.title}" and all its assets/unlocks? This cannot be undone.`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => deleteMut.mutate(m.id) },
    ]);
  };

  const canCreate = title.trim().length > 0 && content.trim().length > 0 && !createMut.isPending;

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
                  <Button size="sm" variant="outline" onPress={pickFile} disabled={uploadMut.isPending} icon={uploadMut.isPending ? <PagePaySpinner size={16} /> : <Ionicons name="cloud-upload-outline" size={16} />}>
                    Upload
                  </Button>
                  <Button size="sm" onPress={() => setShowCreate((v) => !v)} icon={<Ionicons name={showCreate ? "close" : "add"} size={16} color={tokens.mintText} />}>
                    {showCreate ? "Close" : "New"}
                  </Button>
                </View>
              </View>
              <Text className="text-xs text-muted-foreground">Upload a file (PDF/DOCX/TXT/MD) or paste text to generate MCQs, flashcards, and essay questions.</Text>

              <View className="gap-2 rounded-xl border border-border p-3 mt-1">
                <Text className="text-sm font-medium text-foreground">File upload options (optional)</Text>
                <View className="gap-1.5">
                  <Label>Title override</Label>
                  <Input value={fileTitle} onChangeText={setFileTitle} placeholder="Defaults to file name" />
                </View>
                <View className="flex-row gap-2">
                  <View className="flex-1 gap-1.5">
                    <Label>Exam type</Label>
                    <Input value={fileExamType} onChangeText={setFileExamType} placeholder="JAMB, WAEC..." />
                  </View>
                  <View className="flex-1 gap-1.5">
                    <Label>Level</Label>
                    <Input value={fileEducationLevel} onChangeText={setFileEducationLevel} placeholder="secondary..." />
                  </View>
                </View>
                <Text className="text-[11px] text-muted-foreground">These apply when you tap Upload (pdf/docx/txt/md, max 10 MB).</Text>
              </View>

              {showCreate ? (
                <View className="gap-3 rounded-xl border border-border p-3 mt-1">
                  <View className="gap-1.5">
                    <Label>Title</Label>
                    <Input value={title} onChangeText={setTitle} placeholder="e.g. Biology Week 1" />
                  </View>
                  <View className="gap-1.5">
                    <Label>Content</Label>
                    <Input
                      value={content}
                      onChangeText={setContent}
                      placeholder="Paste study material text..."
                      multiline
                      numberOfLines={6}
                      style={{ minHeight: 120, textAlignVertical: "top" }}
                    />
                  </View>
                  <View className="flex-row gap-2">
                    <View className="flex-1 gap-1.5">
                      <Label>Exam type (optional)</Label>
                      <Input value={examType} onChangeText={setExamType} placeholder="JAMB, WAEC..." />
                    </View>
                    <View className="flex-1 gap-1.5">
                      <Label>Level (optional)</Label>
                      <Input value={educationLevel} onChangeText={setEducationLevel} placeholder="secondary..." />
                    </View>
                  </View>
                  <Button
                    onPress={() => createMut.mutate({ title: title.trim(), content: content.trim(), exam_type: examType.trim() || null, education_level: educationLevel.trim() || null })}
                    disabled={!canCreate}
                    icon={createMut.isPending ? <PagePaySpinner size={20} /> : undefined}
                  >
                    {createMut.isPending ? "Creating..." : "Create material"}
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
