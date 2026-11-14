import { useEffect, useState } from "react";
import { ScrollView, View, useWindowDimensions } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Image } from "expo-image";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { PagePay } from "@/constants/theme";
import { fetchMaterialPages, getMaterial, type MaterialPage } from "@/src/shared/api/study";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

const PAGE_BATCH_SIZE = 10;

export default function StudyMaterialFileViewer() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const materialId = Number(id);
  const validId = Number.isSafeInteger(materialId) && materialId > 0;
  const router = useRouter();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const { width: screenWidth } = useWindowDimensions();
  const [pageBatch, setPageBatch] = useState(0);
  const [pages, setPages] = useState<MaterialPage[]>([]);
  const [totalPages, setTotalPages] = useState(0);

  const materialQ = useQuery({
    queryKey: ["study", "material", materialId],
    queryFn: () => getMaterial(materialId),
    enabled: validId,
  });
  const pagesQ = useQuery({
    queryKey: ["study", "material", materialId, "page-images", pageBatch],
    queryFn: () => fetchMaterialPages(materialId, pageBatch * PAGE_BATCH_SIZE + 1, PAGE_BATCH_SIZE),
    enabled: validId && Boolean(materialQ.data?.has_original_file),
  });

  useEffect(() => {
    if (!pagesQ.data) return;
    setTotalPages(pagesQ.data.total);
    setPages((current) => {
      const byPage = new Map(current.map((page) => [page.page, page]));
      for (const page of pagesQ.data.pages) byPage.set(page.page, page);
      return [...byPage.values()].sort((a, b) => a.page - b.page);
    });
  }, [pagesQ.data]);

  const pageWidth = Math.max(220, Math.min(screenWidth - 32, 900));
  const material = materialQ.data;

  return (
    <View className="flex-1 bg-background" style={{ backgroundColor: tokens.paper }}>
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Original pages" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="gap-4 px-4 py-5 pb-10" showsVerticalScrollIndicator={false}>
          {materialQ.isLoading ? (
            <Card className="rounded-2xl p-4"><CardContent className="gap-3 py-0"><Skeleton className="h-6 w-2/3" /><Skeleton className="h-48 w-full" /></CardContent></Card>
          ) : materialQ.error || !material ? (
            <Card className="rounded-2xl p-4">
              <CardContent className="gap-3 py-0">
                <Text className="text-sm text-destructive">{materialQ.error instanceof Error ? materialQ.error.message : "Material not found."}</Text>
                <Button size="sm" className="min-h-9 min-w-0 self-start rounded-lg px-3 py-1" onPress={() => router.back()}>Go back</Button>
              </CardContent>
            </Card>
          ) : (
            <>
              <View className="flex-row items-center justify-between gap-3 px-1">
                <View className="flex-1 gap-1">
                  <Text className="text-base font-semibold text-foreground" numberOfLines={1}>{material.title}</Text>
                  <Text className="text-xs text-muted-foreground">
                    {totalPages ? `${pages.length} of ${totalPages} source pages` : "Original source"}
                  </Text>
                </View>
                <Button
                  size="sm"
                  variant="outline"
                  className="min-h-9 min-w-0 rounded-lg px-3 py-1"
                  textClassName="text-xs"
                  onPress={() => router.push(`/(app)/study/${materialId}/reader` as never)}
                >
                  Explained
                </Button>
              </View>

              {pagesQ.isLoading && pages.length === 0 ? (
                <Card className="rounded-2xl p-4"><CardContent className="gap-3 py-0"><Skeleton className="h-48 w-full" /><Skeleton className="h-48 w-full" /></CardContent></Card>
              ) : null}
              {pagesQ.error ? (
                <Card className="rounded-2xl border-destructive/30 p-4">
                  <CardContent className="gap-2 py-0">
                    <Text className="text-sm text-destructive">{pagesQ.error instanceof Error ? pagesQ.error.message : "Could not load original pages."}</Text>
                    <Button
                      size="sm"
                      variant="outline"
                      className="min-h-8 min-w-0 self-start rounded-lg px-3 py-1"
                      textClassName="text-xs"
                      onPress={() => void pagesQ.refetch()}
                      disabled={pagesQ.isFetching}
                    >
                      Retry
                    </Button>
                  </CardContent>
                </Card>
              ) : null}

              {pages.map((page) => (
                <Card key={page.page} className="overflow-hidden rounded-2xl p-0">
                  <CardContent className="gap-2 p-2">
                    <Text className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Page {page.page}</Text>
                    {page.image_url ? (
                      <Image
                        source={{ uri: page.image_url }}
                        contentFit="contain"
                        style={{
                          width: pageWidth,
                          height: Math.max(240, pageWidth * page.height / Math.max(page.width, 1)),
                          alignSelf: "center",
                        }}
                      />
                    ) : null}
                    {page.is_scan ? <Text className="px-1 text-[10px] text-muted-foreground">Scanned page</Text> : null}
                  </CardContent>
                </Card>
              ))}

              {totalPages === 0 && !pagesQ.isLoading ? (
                <Card className="rounded-2xl p-4">
                  <CardContent className="gap-3 py-0">
                    <Text className="text-sm font-semibold text-foreground">Extracted material</Text>
                    <Text className="text-sm leading-6 text-foreground">{material.content || "No source preview is available for this file type."}</Text>
                  </CardContent>
                </Card>
              ) : null}

              {pages.length < totalPages ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="min-h-9 min-w-0 self-center rounded-lg px-4 py-1"
                  textClassName="text-xs"
                  onPress={() => setPageBatch((batch) => batch + 1)}
                  disabled={pagesQ.isFetching}
                >
                  {pagesQ.isFetching ? "Loading…" : "Load more pages"}
                </Button>
              ) : null}
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
