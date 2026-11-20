import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, View } from "react-native";
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
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { Fonts, PagePay } from "@/constants/theme";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";
import {
  checkLessonAnswer,
  generateLesson,
  getLesson,
  updateLessonProgress,
  type LessonCheckResponse,
} from "@/src/shared/api/study";

type AnyObj = Record<string, any>;

function arr(v: any): any[] {
  return Array.isArray(v) ? v : [];
}
function str(v: any): string {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}
function obj(v: any): AnyObj {
  return v && typeof v === "object" && !Array.isArray(v) ? v : {};
}

function SectionTitle({ icon, title, color }: { icon: any; title: string; color: string }) {
  return (
    <View className="flex-row items-center gap-2">
      <Ionicons name={icon} size={16} color={color} />
      <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</Text>
    </View>
  );
}

function BulletList({ items }: { items: string[] }) {
  const clean = items.map((i) => i.trim()).filter(Boolean);
  if (!clean.length) return null;
  return (
    <View className="gap-1.5">
      {clean.map((it, i) => (
        <View key={i} className="flex-row gap-2">
          <Text className="text-sm text-primary">•</Text>
          <Text className="flex-1 text-sm leading-6 text-foreground">{it}</Text>
        </View>
      ))}
    </View>
  );
}

function CheckBlock({
  label,
  itemType,
  segmentIndex,
  prompt,
  hint,
  materialId,
  initial,
  onResult,
}: {
  label: string;
  itemType: "check" | "guided" | "independent";
  segmentIndex: number;
  prompt: string;
  hint?: string;
  materialId: number;
  initial?: { answer: string; result?: LessonCheckResponse | null };
  onResult: (answer: string, result: LessonCheckResponse) => void;
}) {
  const [answer, setAnswer] = useState(initial?.answer || "");
  const [result, setResult] = useState<LessonCheckResponse | null>(initial?.result || null);
  const mut = useMutation({
    mutationFn: () =>
      checkLessonAnswer(materialId, {
        segment_index: segmentIndex,
        item_type: itemType,
        answer: answer.trim(),
      }),
    onSuccess: (res) => {
      setResult(res);
      onResult(answer.trim(), res);
    },
  });

  useEffect(() => {
    setAnswer(initial?.answer || "");
    setResult(initial?.result || null);
  }, [segmentIndex, itemType, initial?.answer]);

  return (
    <View className="gap-2 rounded-xl border border-border bg-background/70 p-3">
      <Text className="text-sm font-semibold text-foreground">{label}</Text>
      {prompt ? <Text className="text-sm leading-6 text-foreground">{prompt}</Text> : null}
      {hint ? <Text className="text-xs text-muted-foreground">Hint: {hint}</Text> : null}
      <Input
        value={answer}
        onChangeText={setAnswer}
        placeholder="Type your answer..."
        multiline
        editable={!mut.isPending}
        style={{ minHeight: 80, textAlignVertical: "top" }}
      />
      <Button
        size="sm"
        className="min-h-9 min-w-0 self-start rounded-lg px-3 py-1"
        textClassName="text-xs"
        onPress={() => mut.mutate()}
        disabled={mut.isPending || answer.trim().length === 0}
        icon={mut.isPending ? <PagePaySpinner size={14} /> : undefined}
      >
        {mut.isPending ? "Checking..." : "Submit answer"}
      </Button>
      {mut.error ? <Text className="text-xs text-destructive">{(mut.error as Error).message}</Text> : null}
      {result ? (
        <View
          className={`gap-1.5 rounded-lg border p-3 ${
            result.can_continue ? "border-green-600/30 bg-green-600/5" : "border-amber-500/30 bg-amber-500/5"
          }`}
        >
          <Text className="text-sm font-semibold text-foreground">
            {result.correct ? "Good work" : result.correct === false ? "Needs improvement" : "Feedback"}
            {result.can_continue ? " · You can continue" : " · Review and try again"}
          </Text>
          <Text className="text-sm leading-6 text-foreground">{result.feedback}</Text>
          {result.misconception ? (
            <Text className="text-xs text-amber-700">Misconception: {result.misconception}</Text>
          ) : null}
          {result.model_answer ? (
            <View className="gap-1 pt-1">
              <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Model answer</Text>
              <Text className="text-sm leading-6 text-foreground">{result.model_answer}</Text>
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

export default function StudyLessonScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const materialId = Number(id);
  const validId = Number.isSafeInteger(materialId) && materialId > 0;
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;

  const [view, setView] = useState<"intro" | "segment" | "outro">("intro");
  const [segIndex, setSegIndex] = useState(0);
  const [states, setStates] = useState<Record<string, any>>({});

  const q = useQuery({
    queryKey: ["study", "lesson", materialId],
    queryFn: () => getLesson(materialId),
    enabled: validId,
  });

  useEffect(() => {
    if (!q.data) return;
    const p = q.data.progress;
    setStates(p?.segment_states || {});
    const total = arr(obj(q.data.lesson).segments).length;
    if (p?.completed) {
      setView("outro");
      setSegIndex(Math.max(0, total - 1));
    } else if ((p?.current_segment || 0) > 0 || Object.keys(p?.segment_states || {}).length > 0) {
      const idx = Math.min(p?.current_segment || 0, Math.max(0, total - 1));
      setView("segment");
      setSegIndex(idx);
    } else {
      setView("intro");
      setSegIndex(0);
    }
  }, [q.data?.material_id, q.data?.lesson_status, q.data?.lesson ? "has" : "no"]);

  const genMut = useMutation({
    mutationFn: () => generateLesson(materialId),
    onSuccess: (data) => {
      qc.setQueryData(["study", "lesson", materialId], data);
      toast({ title: "Lesson ready", variant: "success" });
    },
    onError: (e: Error) => toast({ title: "Lesson generation failed", description: e.message, variant: "destructive" }),
  });

  const saveProgressMut = useMutation({
    mutationFn: (input: { current_segment: number; segment_states: Record<string, any>; completed?: boolean }) =>
      updateLessonProgress(materialId, input),
    onSuccess: (data) => {
      qc.setQueryData(["study", "lesson", materialId], data);
      setStates(data.progress.segment_states || {});
    },
  });

  const lesson = obj(q.data?.lesson);
  const segments = useMemo(() => arr(lesson.segments).map((s) => obj(s)), [q.data?.lesson]);
  const intro = obj(lesson.intro);
  const outro = obj(lesson.outro);
  const current = obj(segments[segIndex]);
  const segState = obj(states[String(segIndex)]);

  const setSegState = (patch: AnyObj) => {
    setStates((prev) => ({ ...prev, [String(segIndex)]: { ...obj(prev[String(segIndex)]), ...patch } }));
  };

  const canContinueFromSegment = () => {
    const s = obj(states[String(segIndex)]);
    const check = obj(s.check);
    const result = obj(check.result);
    // require a check attempt/result before moving on
    return result && (result.can_continue === true || result.correct === true || result.correct === false || typeof result.feedback === "string");
  };

  const persist = async (nextSeg: number, nextStates: Record<string, any>, completed = false) => {
    try {
      await saveProgressMut.mutateAsync({ current_segment: nextSeg, segment_states: nextStates, completed });
    } catch {
      // non-fatal: local state still allows continuation
    }
  };

  const goNext = async () => {
    const nextStates = { ...states, [String(segIndex)]: { ...obj(states[String(segIndex)]), visited: true } };
    setStates(nextStates);
    if (segIndex < segments.length - 1) {
      const next = segIndex + 1;
      setSegIndex(next);
      setView("segment");
      await persist(next, nextStates, false);
    } else {
      setView("outro");
      await persist(segIndex, nextStates, true);
      toast({ title: "Lesson complete", description: "Great work finishing all parts.", variant: "success" });
    }
  };

  const goPrev = async () => {
    if (view === "outro") {
      setView("segment");
      return;
    }
    if (segIndex > 0) {
      const prev = segIndex - 1;
      setSegIndex(prev);
      setView("segment");
      await persist(prev, states, false);
    } else {
      setView("intro");
      await persist(0, states, false);
    }
  };

  if (!validId) {
    return (
      <View className="flex-1 bg-background" style={{ backgroundColor: tokens.paper }}>
        <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
          <PageHeader title="Lesson" showBack onBack={() => router.back()} tokens={tokens} />
          <View className="flex-1 items-center justify-center p-6">
            <Text className="text-muted-foreground">Invalid material.</Text>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  if (q.isLoading && !q.data) {
    return (
      <View className="flex-1 bg-background" style={{ backgroundColor: tokens.paper }}>
        <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
          <PageHeader title="Lesson" showBack onBack={() => router.back()} tokens={tokens} />
          <View className="flex-1 items-center justify-center gap-3">
            <ActivityIndicator />
            <Text className="text-sm text-muted-foreground">Loading lesson…</Text>
          </View>
        </SafeAreaView>
      </View>
    );
  }

  const hasLesson = !!q.data?.lesson && segments.length > 0;
  const status = q.data?.lesson_status;
  const lessonError = q.data?.lesson_error;
  const progressPct =
    view === "intro" ? 5 : view === "outro" ? 100 : Math.round(((segIndex + 1) / Math.max(segments.length, 1)) * 100);

  return (
    <View className="flex-1 bg-background" style={{ backgroundColor: tokens.paper }}>
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title={str(intro.title) || "Lesson"} showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView
          className="flex-1"
          contentContainerClassName="gap-4 px-4 py-5 pb-10"
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {q.error ? (
            <Card className="rounded-2xl p-4">
              <CardContent className="gap-3 py-0">
                <Text className="text-sm text-destructive">{(q.error as Error).message}</Text>
                <Button size="sm" variant="outline" className="self-start rounded-lg" onPress={() => q.refetch()}>
                  Retry
                </Button>
              </CardContent>
            </Card>
          ) : null}

          {!hasLesson ? (
            <Card className="rounded-2xl p-4">
              <CardContent className="gap-3 py-0">
                <Text className="text-base font-semibold text-foreground" style={{ fontFamily: Fonts.editorialSemiBold as string }}>
                  Interactive lesson
                </Text>
                <Text className="text-sm leading-6 text-muted-foreground">
                  Learn in short cycles: each part sets a goal, presents a small chunk, explains it in plain language with
                  examples, models the thinking, checks your understanding, gives guided then independent practice, and recaps
                  before moving on.
                </Text>
                {status === "generating" ? (
                  <Text className="text-xs text-muted-foreground">Lesson is being prepared… this can take a few minutes.</Text>
                ) : null}
                {status === "failed" && lessonError ? (
                  <Text className="text-xs text-destructive">Could not prepare lesson: {lessonError}</Text>
                ) : null}
                <Button
                  className="min-h-10 self-start rounded-lg px-4"
                  onPress={() => genMut.mutate()}
                  disabled={genMut.isPending || status === "generating"}
                  icon={
                    genMut.isPending ? <PagePaySpinner size={16} /> : <Ionicons name="sparkles-outline" size={16} color={tokens.mintText} />
                  }
                >
                  {genMut.isPending ? "Preparing lesson..." : "Prepare interactive lesson"}
                </Button>
                <Text className="text-xs text-muted-foreground">
                  Your original content remains available in Read material / Original pages.
                </Text>
              </CardContent>
            </Card>
          ) : (
            <>
              <View className="gap-2">
                <View className="flex-row items-center justify-between">
                  <Text className="text-xs font-medium text-muted-foreground">
                    {view === "intro" ? "Introduction" : view === "outro" ? "Summary" : `Part ${segIndex + 1} of ${segments.length}`}
                  </Text>
                  <Text className="text-xs text-muted-foreground">{segments.length} parts</Text>
                </View>
                <View className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <View className="h-full rounded-full bg-primary" style={{ width: `${progressPct}%` }} />
                </View>
              </View>

              {view === "intro" ? (
                <Card className="rounded-2xl p-4">
                  <CardContent className="gap-4 py-0">
                    <SectionTitle icon="flag-outline" title="What you will learn" color={tokens.mint} />
                    <BulletList items={arr(intro.goals).map(str)} />
                    {str(intro.why_it_matters) ? (
                      <>
                        <SectionTitle icon="bulb-outline" title="Why it matters" color={tokens.mint} />
                        <Text className="text-sm leading-6 text-foreground">{str(intro.why_it_matters)}</Text>
                      </>
                    ) : null}
                    {arr(intro.prior_knowledge).length ? (
                      <>
                        <SectionTitle icon="link-outline" title="Recall first" color={tokens.mint} />
                        <BulletList items={arr(intro.prior_knowledge).map(str)} />
                      </>
                    ) : null}
                    {str(intro.overview) ? (
                      <>
                        <SectionTitle icon="map-outline" title="Lesson overview" color={tokens.mint} />
                        <Text className="text-sm leading-6 text-foreground">{str(intro.overview)}</Text>
                      </>
                    ) : null}
                    <Button className="mt-2 rounded-lg" onPress={() => { setView("segment"); setSegIndex(0); }}>
                      Start learning
                    </Button>
                  </CardContent>
                </Card>
              ) : null}

              {view === "segment" ? (
                <View className="gap-4">
                  <Card className="rounded-2xl p-4">
                    <CardContent className="gap-3 py-0">
                      <Text className="text-xs font-semibold uppercase tracking-wide text-primary">Micro-goal</Text>
                      <Text className="text-base font-semibold text-foreground" style={{ fontFamily: Fonts.editorialSemiBold as string }}>
                        {str(current.micro_goal) || str(current.title) || `Part ${segIndex + 1}`}
                      </Text>
                      {str(current.source_chunk) ? (
                        <>
                          <SectionTitle icon="document-text-outline" title="Source chunk" color={tokens.mint} />
                          <Text className="text-sm leading-6 text-muted-foreground">{str(current.source_chunk)}</Text>
                        </>
                      ) : null}
                      {arr(current.key_terms).length ? (
                        <>
                          <SectionTitle icon="pricetag-outline" title="Key terms (defined first)" color={tokens.mint} />
                          <View className="gap-2">
                            {arr(current.key_terms).map((t: any, i: number) => {
                              const to = obj(t);
                              const term = str(to.term);
                              const def = str(to.definition);
                              if (!term && !def) return null;
                              return (
                                <View key={i} className="rounded-lg border border-border bg-background p-2">
                                  <Text className="text-sm font-semibold text-foreground">{term}</Text>
                                  <Text className="text-sm leading-6 text-muted-foreground">{def}</Text>
                                </View>
                              );
                            })}
                          </View>
                        </>
                      ) : null}
                    </CardContent>
                  </Card>

                  <Card className="rounded-2xl p-4">
                    <CardContent className="gap-3 py-0">
                      <SectionTitle icon="school-outline" title="Explanation" color={tokens.mint} />
                      {str(current.explanation) ? <Text className="text-sm leading-6 text-foreground">{str(current.explanation)}</Text> : null}
                      {str(current.example) ? (
                        <>
                          <SectionTitle icon="sparkles-outline" title="Example / analogy" color={tokens.mint} />
                          <Text className="text-sm leading-6 text-foreground">{str(current.example)}</Text>
                        </>
                      ) : null}
                      {str(current.modeled_thinking) ? (
                        <>
                          <SectionTitle icon="chatbubble-ellipses-outline" title="Model thinking" color={tokens.mint} />
                          <Text className="text-sm leading-6 text-foreground">{str(current.modeled_thinking)}</Text>
                        </>
                      ) : null}
                      {arr(current.worked_steps).map(str).filter(Boolean).length ? (
                        <>
                          <SectionTitle icon="list-outline" title="Worked steps" color={tokens.mint} />
                          <BulletList items={arr(current.worked_steps).map(str)} />
                        </>
                      ) : null}
                    </CardContent>
                  </Card>

                  {str(obj(current.check).question) ? (
                    <CheckBlock
                      label="Check understanding (required to continue)"
                      itemType="check"
                      segmentIndex={segIndex}
                      materialId={materialId}
                      prompt={str(obj(current.check).question)}
                      initial={{ answer: str(obj(segState.check).answer), result: obj(segState.check).result as any }}
                      onResult={(answer, result) => setSegState({ check: { answer, result } })}
                    />
                  ) : null}

                  {str(obj(current.guided_practice).prompt) ? (
                    <CheckBlock
                      label="Guided practice"
                      itemType="guided"
                      segmentIndex={segIndex}
                      materialId={materialId}
                      prompt={str(obj(current.guided_practice).prompt)}
                      hint={str(obj(current.guided_practice).hint) || undefined}
                      initial={{ answer: str(obj(segState.guided).answer), result: obj(segState.guided).result as any }}
                      onResult={(answer, result) => setSegState({ guided: { answer, result } })}
                    />
                  ) : null}

                  {str(obj(current.independent_practice).prompt) ? (
                    <CheckBlock
                      label="Independent practice"
                      itemType="independent"
                      segmentIndex={segIndex}
                      materialId={materialId}
                      prompt={str(obj(current.independent_practice).prompt)}
                      initial={{ answer: str(obj(segState.independent).answer), result: obj(segState.independent).result as any }}
                      onResult={(answer, result) => setSegState({ independent: { answer, result } })}
                    />
                  ) : null}

                  {str(current.bridge_recap) ? (
                    <Card className="rounded-2xl p-4">
                      <CardContent className="gap-2 py-0">
                        <SectionTitle icon="git-merge-outline" title="Bridge & recap" color={tokens.mint} />
                        <Text className="text-sm leading-6 text-foreground">{str(current.bridge_recap)}</Text>
                      </CardContent>
                    </Card>
                  ) : null}

                  {!canContinueFromSegment() ? (
                    <Text className="text-xs text-amber-600">Complete the “Check understanding” step to continue.</Text>
                  ) : null}

                  <View className="flex-row gap-2">
                    <Button size="sm" variant="outline" className="flex-1 rounded-lg" onPress={() => void goPrev()}>
                      Back
                    </Button>
                    <Button
                      size="sm"
                      className="flex-1 rounded-lg"
                      onPress={() => void goNext()}
                      disabled={!canContinueFromSegment() || saveProgressMut.isPending}
                    >
                      {segIndex < segments.length - 1 ? "Next part" : "Finish lesson"}
                    </Button>
                  </View>
                </View>
              ) : null}

              {view === "outro" ? (
                <Card className="rounded-2xl p-4">
                  <CardContent className="gap-4 py-0">
                    <SectionTitle icon="trophy-outline" title="Key takeaways" color={tokens.mint} />
                    <BulletList items={arr(outro.summary).map(str)} />
                    {arr(outro.common_pitfalls).length ? (
                      <>
                        <SectionTitle icon="warning-outline" title="Common pitfalls" color={tokens.mint} />
                        <BulletList items={arr(outro.common_pitfalls).map(str)} />
                      </>
                    ) : null}
                    {str(outro.next_steps) ? (
                      <>
                        <SectionTitle icon="arrow-forward-circle-outline" title="Next steps" color={tokens.mint} />
                        <Text className="text-sm leading-6 text-foreground">{str(outro.next_steps)}</Text>
                      </>
                    ) : null}
                    <View className="flex-row gap-2 pt-2">
                      <Button size="sm" variant="outline" className="flex-1 rounded-lg" onPress={() => { setView("segment"); setSegIndex(Math.max(0, segments.length - 1)); }}>
                        Review last part
                      </Button>
                      <Button size="sm" className="flex-1 rounded-lg" onPress={() => router.replace(`/(app)/study/${materialId}` as any)}>
                        Back to material
                      </Button>
                    </View>
                  </CardContent>
                </Card>
              ) : null}

              <Pressable onPress={() => router.push(`/(app)/study/${materialId}/reader` as never)} className="self-center py-2">
                <Text className="text-xs text-muted-foreground underline">Open original/explained content (reader)</Text>
              </Pressable>
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
