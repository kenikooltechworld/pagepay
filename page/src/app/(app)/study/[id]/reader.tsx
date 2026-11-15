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
import { RichText } from "@/components/study/RichText";
import { SpecialBlockCard, type ContentBlock as StudyContentBlock } from "@/components/study/SpecialBlockCard";
import { Fonts, PagePay } from "@/constants/theme";
import { fetchMaterialFigures, getMaterial, type MaterialFigure } from "@/src/shared/api/study";
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

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function stringRows(value: unknown): string[][] {
  if (!Array.isArray(value)) return [];
  return value.map((row) => textList(row));
}

function toStudyContentBlock(block: JsonObject): StudyContentBlock {
  return {
    type: asText(block.type),
    text: asText(block.text),
    level: asNumber(block.level),
    items: textList(block.items),
    label: asText(block.label),
    steps: textList(block.steps),
    language: asText(block.language),
    attribution: asText(block.attribution),
    description: asText(block.description),
    term: asText(block.term),
    headers: textList(block.headers),
    rows: stringRows(block.rows),
  };
}

function ContentBlock({
  value,
  index,
  figures,
  tokens,
}: {
  value: unknown;
  index: number;
  figures: MaterialFigure[];
  tokens: (typeof PagePay)["light"];
}) {
  const block = asObject(value);
  if (!block) return null;
  const type = asText(block.type);
  const text = asText(block.text);
  const items = textList(block.items);

  if (type === "heading") {
    const level = asNumber(block.level) ?? 2;
    return (
      <Text
        className={`font-semibold text-foreground ${level === 1 ? "text-xl" : level === 3 ? "text-base" : "text-lg"}`}
        style={{ fontFamily: Fonts.editorialSemiBold as string }}
      >
        {text}
      </Text>
    );
  }
  if (type === "body") {
    return <RichText color={tokens.ink} fontSize={15} lineHeight={24}>{text}</RichText>;
  }
  if (type === "list" || type === "numbered_list" || type === "recap") {
    return (
      <View className="gap-2 rounded-xl border border-border bg-background/70 p-3">
        {type === "recap" ? <Text className="text-xs font-semibold uppercase tracking-wide text-primary">Key takeaways</Text> : null}
        {items.map((item, itemIndex) => (
          <View key={`${index}-${itemIndex}`} className="flex-row gap-2">
            <Text className="text-sm leading-6 text-primary">
              {type === "numbered_list" ? `${itemIndex + 1}.` : "•"}
            </Text>
            <RichText color={tokens.ink} fontSize={14} lineHeight={22}>{item}</RichText>
          </View>
        ))}
      </View>
    );
  }
  if (type === "figure") {
    const requestedIndex = asNumber(block.figure_index);
    const figure = requestedIndex
      ? figures.find((item) => item.figure_index === requestedIndex - 1)
        ?? figures.find((item) => item.figure_index === requestedIndex)
      : undefined;
    const page = asNumber(block.page) ?? figure?.page;
    const caption = asText(block.caption) || figure?.caption || "";
    const description = text || figure?.description || "";
    return (
      <Card className="overflow-hidden rounded-xl p-2">
        <CardContent className="gap-2 py-0">
          {figure?.image_url ? (
            <Image source={{ uri: figure.image_url }} contentFit="contain" style={{ width: "100%", height: 220 }} />
          ) : null}
          {caption ? <Text className="text-sm font-semibold text-foreground">{caption}</Text> : null}
          {description ? <Text className="text-sm leading-6 text-muted-foreground">{description}</Text> : null}
          {!caption && !description && page ? <Text className="text-xs text-muted-foreground">Figure from page {page}</Text> : null}
        </CardContent>
      </Card>
    );
  }
  if (["tip", "warning", "calculation", "code", "quote", "formula", "statement", "definition", "table"].includes(type)) {
    return <SpecialBlockCard block={toStudyContentBlock(block)} tokens={tokens} index={index} />;
  }
  if (text) return <RichText color={tokens.ink} fontSize={15} lineHeight={24}>{text}</RichText>;
  return null;
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
  const blocks = Array.isArray(explanation?.content_blocks) ? explanation.content_blocks : [];
  const referencedFigureIndexes = new Set<number>();
  for (const value of blocks) {
    const block = asObject(value);
    const figureIndex = asNumber(block?.figure_index);
    if (asText(block?.type) === "figure" && figureIndex && figureIndex > 0) {
      referencedFigureIndexes.add(figureIndex - 1);
    }
  }
  const additionalFigures = (figuresQ.data ?? []).filter(
    (figure) => !referencedFigureIndexes.has(figure.figure_index),
  );

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
                    {blocks.map((block, index) => (
                      <ContentBlock
                        key={`block-${index}`}
                        value={block}
                        index={index}
                        figures={figuresQ.data ?? []}
                        tokens={tokens}
                      />
                    ))}
                  </View>
                ) : (
                  <Card className="rounded-2xl border-destructive/30 p-4">
                    <CardContent className="py-0">
                      <Text className="text-sm leading-6 text-destructive">
                        The server returned no formatted explanation for this material.
                      </Text>
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
              {mode === "explained" && additionalFigures.length > 0 ? (
                <Card className="rounded-2xl p-3">
                  <CardContent className="gap-3 py-0">
                    <Text className="text-sm font-semibold text-foreground">Figures and diagrams</Text>
                    {additionalFigures.map((figure) => (
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
