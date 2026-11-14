import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { Fonts, PagePay } from "@/constants/theme";
import { fetchMaterialFigures, getMaterial } from "@/src/shared/api/study";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

type JsonObject = Record<string, unknown>;

function asObject(value: unknown): JsonObject | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as JsonObject
    : null;
}

function asText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function ContentBlock({ value, index }: { value: unknown; index: number }) {
  const block = asObject(value);
  if (!block) return null;
  const type = asText(block.type);
  const text = asText(block.text);
  const items = textList(block.items);

  if (type === "heading") {
    return (
      <Text
        className="text-lg font-semibold text-foreground"
        style={{ fontFamily: Fonts.editorialSemiBold as string }}
      >
        {text}
      </Text>
    );
  }
  if (type === "list" || type === "numbered_list" || type === "recap") {
    return (
      <View className="gap-2 rounded-xl border border-border bg-background/70 p-3">
        {type === "recap" ? <Text className="text-xs font-semibold uppercase tracking-wide text-primary">Key takeaways</Text> : null}
        {items.map((item, itemIndex) => (
          <Text key={`${index}-${itemIndex}`} className="text-sm leading-6 text-foreground">
            {type === "numbered_list" ? `${itemIndex + 1}. ` : "• "}{item}
          </Text>
        ))}
      </View>
    );
  }
  if (type === "tip" || type === "warning" || type === "definition") {
    const label = type === "tip" ? "Study tip" : type === "warning" ? "Important" : "Definition";
    return (
      <View className="gap-1 rounded-xl border border-primary/20 bg-primary/5 p-3">
        <Text className="text-xs font-semibold uppercase tracking-wide text-primary">{label}</Text>
        <Text className="text-sm leading-6 text-foreground">{text}</Text>
      </View>
    );
  }
  if (text) return <Text className="text-sm leading-6 text-foreground">{text}</Text>;
  return null;
}

function ParsedOutline({ structure }: { structure: JsonObject | null }) {
  if (!structure) return null;
  const topics = Array.isArray(structure.topics) ? structure.topics : [];
  const summary = asText(structure.summary);
  return (
    <View className="gap-4">
      {summary ? <Text className="text-sm leading-6 text-foreground">{summary}</Text> : null}
      {topics.map((value, index) => {
        const topic = asObject(value);
        if (!topic) return null;
        const subtopics = textList(topic.subtopics);
        const points = textList(topic.key_points);
        return (
          <View key={`topic-${index}`} className="gap-2 rounded-xl border border-border bg-background/70 p-3">
            <Text className="text-base font-semibold text-foreground">{asText(topic.name) || `Topic ${index + 1}`}</Text>
            {subtopics.map((item, itemIndex) => (
              <Text key={`subtopic-${itemIndex}`} className="text-sm leading-5 text-muted-foreground">• {item}</Text>
            ))}
            {points.length ? (
              <View className="gap-1 border-t border-border pt-2">
                <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Key points</Text>
                {points.map((item, itemIndex) => (
                  <Text key={`point-${itemIndex}`} className="text-sm leading-5 text-foreground">• {item}</Text>
                ))}
              </View>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

export default function StudyMaterialReader() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const materialId = Number(id);
  const validId = Number.isSafeInteger(materialId) && materialId > 0;
  const router = useRouter();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [mode, setMode] = useState<"explained" | "source">("explained");

  const materialQ = useQuery({
    queryKey: ["study", "material", materialId],
    queryFn: () => getMaterial(materialId),
    enabled: validId,
  });
  const figuresQ = useQuery({
    queryKey: ["study", "material", materialId, "figures"],
    queryFn: () => fetchMaterialFigures(materialId),
    enabled: validId && mode === "explained" && Boolean(materialQ.data?.has_original_file),
  });
  const material = materialQ.data;
  const explanation = asObject(material?.explanation_structure);
  const parsed = asObject(material?.parsed_structure);
  const blocks = Array.isArray(explanation?.content_blocks) ? explanation.content_blocks : [];

  return (
    <View className="flex-1 bg-background" style={{ backgroundColor: tokens.paper }}>
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Material reader" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="gap-4 px-4 py-5 pb-10" showsVerticalScrollIndicator={false}>
          {materialQ.isLoading ? (
            <Card className="rounded-2xl p-4"><CardContent className="gap-3 py-0"><Skeleton className="h-6 w-2/3" /><Skeleton className="h-24 w-full" /></CardContent></Card>
          ) : materialQ.error || !material ? (
            <Card className="rounded-2xl p-4">
              <CardContent className="gap-3 py-0">
                <Text className="text-sm text-destructive">{materialQ.error instanceof Error ? materialQ.error.message : "Material not found."}</Text>
                <Button size="sm" className="min-h-9 min-w-0 self-start rounded-lg px-3 py-1" onPress={() => router.back()}>Go back</Button>
              </CardContent>
            </Card>
          ) : (
            <>
              <View className="gap-1 px-1">
                <Text className="text-xl font-semibold text-foreground" style={{ fontFamily: Fonts.editorialSemiBold as string }}>
                  {material.title}
                </Text>
                <Text className="text-xs text-muted-foreground">
                  {[material.exam_type, material.education_level].filter(Boolean).join(" · ") || "Study material"}
                </Text>
              </View>
              <View className="flex-row gap-2">
                <Pressable
                  onPress={() => setMode("explained")}
                  className={`flex-1 flex-row items-center justify-center gap-1.5 rounded-lg border px-3 py-2 ${mode === "explained" ? "border-primary bg-primary/10" : "border-border bg-background"}`}
                  accessibilityRole="button"
                  accessibilityState={{ selected: mode === "explained" }}
                >
                  <Ionicons name="school-outline" size={15} color={mode === "explained" ? tokens.mint : tokens.inkMuted} />
                  <Text className={`text-xs font-medium ${mode === "explained" ? "text-primary" : "text-muted-foreground"}`}>Explained</Text>
                </Pressable>
                <Pressable
                  onPress={() => setMode("source")}
                  className={`flex-1 flex-row items-center justify-center gap-1.5 rounded-lg border px-3 py-2 ${mode === "source" ? "border-primary bg-primary/10" : "border-border bg-background"}`}
                  accessibilityRole="button"
                  accessibilityState={{ selected: mode === "source" }}
                >
                  <Ionicons name="document-text-outline" size={15} color={mode === "source" ? tokens.mint : tokens.inkMuted} />
                  <Text className={`text-xs font-medium ${mode === "source" ? "text-primary" : "text-muted-foreground"}`}>Original text</Text>
                </Pressable>
              </View>

              {mode === "explained" ? (
                blocks.length ? (
                  <View className="gap-3">
                    {blocks.map((block, index) => <ContentBlock key={`block-${index}`} value={block} index={index} />)}
                  </View>
                ) : parsed ? (
                  <ParsedOutline structure={parsed} />
                ) : (
                  <Card className="rounded-2xl p-4">
                    <CardContent className="py-0">
                      <Text className="text-sm leading-6 text-foreground">{material.content || "No readable content was saved for this material."}</Text>
                    </CardContent>
                  </Card>
                )
              ) : (
                <Card className="rounded-2xl p-4">
                  <CardContent className="py-0">
                    <Text className="text-sm leading-6 text-foreground">{material.content || "No extracted text is available."}</Text>
                  </CardContent>
                </Card>
              )}

              {mode === "explained" && figuresQ.error ? (
                <Card className="rounded-2xl border-destructive/30 p-3">
                  <CardContent className="py-0">
                    <Text className="text-xs text-destructive">
                      {figuresQ.error instanceof Error ? figuresQ.error.message : "Could not load document figures."}
                    </Text>
                  </CardContent>
                </Card>
              ) : null}
              {mode === "explained" && (figuresQ.data?.length ?? 0) > 0 ? (
                <Card className="rounded-2xl p-3">
                  <CardContent className="gap-3 py-0">
                    <Text className="text-sm font-semibold text-foreground">Figures and diagrams</Text>
                    {figuresQ.data?.map((figure) => (
                      <View key={figure.figure_index} className="gap-2 rounded-xl border border-border bg-background/70 p-2">
                        {figure.image_url ? (
                          <Image source={{ uri: figure.image_url }} contentFit="contain" style={{ width: "100%", height: 220 }} />
                        ) : null}
                        <Text className="text-xs text-muted-foreground">
                          {figure.caption || figure.description || `From page ${figure.page}`}
                        </Text>
                      </View>
                    ))}
                  </CardContent>
                </Card>
              ) : null}

              {material.has_original_file ? (
                <Card className="rounded-2xl p-3">
                  <CardContent className="flex-row items-center justify-between gap-3 py-0">
                    <View className="flex-1 gap-1">
                      <Text className="text-sm font-semibold text-foreground">Source document</Text>
                      <Text className="text-xs text-muted-foreground">
                        {material.page_count ? `${material.page_count} pages processed` : "Original file attached"}
                      </Text>
                    </View>
                    <Button
                      size="sm"
                      variant="outline"
                      className="min-h-9 min-w-0 rounded-lg px-3 py-1"
                      textClassName="text-xs"
                      onPress={() => router.push(`/(app)/study/${materialId}/file-viewer` as never)}
                    >
                      View pages
                    </Button>
                  </CardContent>
                </Card>
              ) : null}
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
