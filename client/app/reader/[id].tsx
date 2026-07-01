import { useState, useEffect, useRef } from 'react';
import { View, Text, ScrollView, StyleSheet, AppState, AppStateStatus, Platform, TouchableOpacity } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/src/shared/api/client';
import { MockAdModal } from '@/components/MockAdModal';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type ContentDetail = {
  id: number;
  title: string;
  content_type: string;
  category: string;
  author: string | null;
  body_text: string | null;
  estimated_read_minutes: number;
  is_sponsored: boolean;
  // Id of the parent work — set on sliced children, null on standalone.
  // The reader uses this to navigate back to the book detail screen
  // after finishing a slice.
  parent_work_id: number | null;
};

type ContinueReading = {
  slice_id: number | null;
  work_id: number | null;
  work_title: string | null;
  slice_title: string | null;
  slice_order: number;
  total_slices: number;
  percent_complete: number;
  has_in_progress: boolean;
  scroll_offset_px: number;
};

type SessionEndResponse = {
  requires_claim: boolean;
  pending_points: number;
  session_id: number;
  verified: boolean;
};

/**
 * Reader screen with a reward gate at both ends of the session.
 *
 * Flow:
 *   1. Mount → fetch content + progress (resume offset).
 *   2. PRE-READ GATE (ad #1): show MockAdModal. On claim →
 *      POST /session/start → unlock the timer + heartbeat.
 *      On skip → bounce to home (no session row created, no points).
 *   3. Active reading: heartbeat every 10s, scroll-track, visible
 *      timer ticks (1s) up to 60s, then the inline Finish button
 *      unlocks.
 *   4. Tap Finish → POST-READ GATE (ad #2): show MockAdModal FIRST.
 *      On claim → POST /session/end (stages pending_points) →
 *      auto-POST /session/claim (credits the wallet) → POST
 *      /progress/finish (advance the slice pointer) → navigate to
 *      the book detail.
 *      On skip → POST /session/end still fires (we advance the slice
 *      pointer), but /session/claim is skipped → user forfeits the
 *      staged points. Still navigates back to the book detail.
 *
 * Why ad #2 sits BEFORE /session/end: the user explicitly said the
 * second ad should gate the end-of-session, not sit after it. Putting
 * it first means the user's act of "finishing" is driven by watching
 * (or skipping) the ad, not by tapping Finish alone.
 *
 * Why we don't block skip on claiming: the user already did the read;
 * making them sit through a third modal to confirm forfeit would be
 * punitive. Skip forfeits the points but never stalls the flow.
 */
export default function ReaderScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  // Invalidate ['me'] after every ad credit so the home chip + wallet
  // tab reflect the new points balance immediately. Without this, the
  // user would have to pull-to-refresh to see points land.
  const queryClient = useQueryClient();
  // Theme tokens — the reader is meant to feel like the rest of the app,
  // not a hardcoded white slab. Keeping the surface paper-toned in both
  // schemes so reading doesn't feel like a separate app.
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const [content, setContent] = useState<ContentDetail | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const [loading, setLoading] = useState(true);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  // Pre-read gate: unlocks the session timer.
  const [preReadOpen, setPreReadOpen] = useState(true);
  // Post-read gate: sits BEFORE /session/end, not after. The user has
  // read for the 1-minute floor — now they watch (or skip) a second ad
  // to "fire" the end-of-session sequence. The server still recalculates
  // and stages pending_points inside /session/end; the auto-claim after
  // /session/end closes the loop without surfacing a third modal.
  const [postReadAdOpen, setPostReadAdOpen] = useState(false);

  const appState = useRef(AppState.currentState);
  const heartbeatRef = useRef<number | null>(null);
  const scrollCount = useRef(0);
  const sessionIdRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const scrollRef = useRef<ScrollView | null>(null);
  const lastSavedOffset = useRef(0);
  // Single one-shot latch for the inline Finish button so a double-tap
  // can't fire `triggerFinish` twice. Reset whenever the slice id changes.
  const finishFiredRef = useRef(false);
  // One-shot latch for the screen-unmount cleanup. After the user has
  // manually finished (or the post-finish modal has surfaced), the cleanup
  // MUST NOT call `endSession` again — that double-fires /session/end,
  // extends the session's end_time server-side, and reopens the post-finish
  // modal on a screen the user has already navigated away from (causing
  // the visible flicker back to Home).
  const finishedManuallyRef = useRef(false);

  // Load content + resume metadata once on mount. Session creation is
  // deferred until the user clears the pre-read gate.
  useEffect(() => {
    let mounted = true;

    const loadContent = async () => {
      const res = await apiFetch(`/api/v1/content/${id}`);
      const data = (await res.json()) as ContentDetail;
      if (mounted) {
        setContent(data);
        setLoading(false);
      }
    };

    loadContent();
    finishFiredRef.current = false;
    finishedManuallyRef.current = false;

    // Pick up an existing in-progress work so we can restore scroll offset.
    (async () => {
      try {
        const r = await apiFetch('/api/v1/progress/continue');
        if (!r.ok) return;
        const ct = r.headers.get('content-type') ?? '';
        if (!ct.includes('application/json')) return;
        const data = (await r.json()) as ContinueReading;
        const sliceIdNum = Number(id);
        if (data.has_in_progress && data.slice_id === sliceIdNum && data.scroll_offset_px > 0) {
          // Defer until the ScrollView is mounted.
          setTimeout(() => {
            scrollRef.current?.scrollTo({ y: data.scroll_offset_px, animated: false });
          }, 250);
        }
        if (data.has_in_progress && data.work_id && data.slice_id === sliceIdNum) {
          // Ensure tracking row exists (idempotent).
          await apiFetch(`/api/v1/progress/start?work_id=${data.work_id}`, { method: 'POST' });
        }
      } catch (e) {
        console.warn('Resume check failed', e);
      }
    })();

    return () => {
      mounted = false;
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
      // Only auto-end the session on screen teardown if the user has NOT
      // already finished manually. The manual path (Finish & claim, Skip,
      // no-claim advance) handles /session/end itself — the cleanup must
      // not fire it again or we get:
      //   - a duplicate /session/end (server extends end_time silently),
      //   - a duplicate /progress/finish (when the second response hits
      //     the no-claim branch),
      //   - and worst, the catch block in `endSession`'s
      //     router.replace('/(tabs)') firing on a slow network response,
      //     which is the visible flicker back to Home that the user
      //     reported.
      if (sessionIdRef.current && !finishedManuallyRef.current) {
        endSession(sessionIdRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Heartbeat + elapsed timer start AFTER the pre-read gate clears.
  useEffect(() => {
    if (!sessionId) return;

    heartbeatRef.current = setInterval(() => {
      sendHeartbeat();
    }, 10000);

    timerRef.current = setInterval(() => {
      // Pause the visible timer at the 1-minute mark. The reader is
      // meant to keep reading or tap Finish — the timer stopping
      // signals "1 minute done, your reward is ready." We don't kill
      // the heartbeat interval; the server keeps tracking real elapsed
      // time and re-claims when the user finishes.
      setElapsedSeconds((s) => (s < 60 ? s + 1 : s));
    }, 1000);

    return () => {
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [sessionId]);

  const sendHeartbeat = async () => {
    if (!sessionIdRef.current) return;
    try {
      const res = await apiFetch('/api/v1/session/heartbeat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          scroll_events: scrollCount.current,
          app_state: appState.current === 'active' ? 'active' : 'background',
        }),
      });
      const ct = res.headers.get('content-type') ?? '';
      if (!ct.includes('application/json')) {
        return;
      }
      const json = await res.json();
      setPaused(json.paused);
    } catch (e) {
      console.error('Heartbeat failed', e);
    }
    scrollCount.current = 0;
  };

  const startSession = async () => {
    const res = await apiFetch('/api/v1/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content_id: Number(id) }),
    });
    const json = await res.json();
    setSessionId(json.session_id);
    sessionIdRef.current = json.session_id;
  };

  const endSession = async (sid: number) => {
    try {
      // Manual finish path: endSession is being driven by the user
      // (Finish & claim, Skip, no-claim advance). Mark the session as
      // "manually finished" so the unmount cleanup at the top of this file
      // does NOT call endSession a second time as the screen tears down.
      // Without this, the cleanup would re-POST /session/end after we've
      // already navigated, and on a slow network the catch block's
      // router.replace('/(tabs)') would visibly flicker the user back to
      // Home after they just landed on the book detail.
      finishedManuallyRef.current = true;
      const res = await apiFetch('/api/v1/session/end', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid }),
      });
      const ct = res.headers.get('content-type') ?? '';
      if (!ct.includes('application/json')) {
        const body = await res.text();
        console.error(
          `End session: non-JSON response (${res.status}) from /session/end: ${body.slice(0, 200)}`,
        );
        return;
      }
      const json = (await res.json()) as SessionEndResponse;
      // Two-stage close:
      //   1. /session/end STAGED pending_points but did not credit.
      //   2. If the user earned anything, /session/claim credits it
      //      automatically. The post-read ad already played — we don't
      //      surface a third modal after the user has watched the ad.
      //   3. /progress/finish advances the slice pointer regardless of
      //      whether the session earned points (skipped or too-short
      //      sessions still advance — the user did the read).
      if (json.requires_claim && json.pending_points > 0) {
        try {
          await apiFetch('/api/v1/session/claim', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid }),
          });
        } catch (e) {
          console.warn('Auto-claim after end failed', e);
        }
      }
      try {
        await apiFetch(`/api/v1/progress/finish?slice_id=${Number(id)}`, { method: 'POST' });
      } catch (e) {
        console.warn('Progress finish failed', e);
      }
      // Return to the book detail so the user sees the next slice
      // unlocked and chooses when to start it.
      const parentId = content?.parent_work_id;
      if (parentId) {
        router.replace(`/book/${parentId}` as never);
      } else {
        router.replace('/(tabs)');
      }
    } catch (e) {
      console.error('End session failed', e);
      router.replace('/(tabs)');
    }
  };

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextState: AppStateStatus) => {
      appState.current = nextState;
      if (nextState === 'active' && sessionIdRef.current) {
        sendHeartbeat();
      }
    });
    return () => subscription.remove();
  }, []);

  // The Finish button is inline at the end of the slice body now — it
  // doesn't need to react to scroll position or elapsed time. The user
  // taps it whenever they feel done. Anti-cheat on the server (verified
  // duration + scroll events) decides whether points are credited.
  const handleScroll = (e: { nativeEvent: { contentOffset: { y: number }; contentSize: { height: number }; layoutMeasurement: { height: number } } }) => {
    scrollCount.current += 1;
    const y = e.nativeEvent.contentOffset.y;
    if (Math.abs(y - lastSavedOffset.current) >= 300) {
      lastSavedOffset.current = y;
      saveBookmarkDebounced(y);
    }
  };

  const saveBookmarkDebounced = (() => {
    let pending: ReturnType<typeof setTimeout> | null = null;
    return (offset: number) => {
      if (pending) clearTimeout(pending);
      pending = setTimeout(() => {
        apiFetch('/api/v1/progress/bookmark', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slice_id: Number(id), scroll_offset_px: Math.floor(offset) }),
        }).catch(() => {});
      }, 500);
    };
  })();

  /**
   * Tear down the active heartbeat and surface the post-read ad modal.
   * The modal sits BEFORE /session/end now — the user watches (or skips)
   * the ad, then the close-out sequence runs end → auto-claim → progress
   * → navigate. endSession is called from the modal's onClaim / onSkip,
   * not from here.
   */
  const triggerFinish = async () => {
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    if (timerRef.current) clearInterval(timerRef.current);
    heartbeatRef.current = null;
    timerRef.current = null;

    if (sessionIdRef.current) {
      // Mark manually-finished as soon as the post-read modal opens.
      // The user is committed to closing the session; if the reader
      // unmounts before they tap Claim/Skip, cleanup must NOT fire
      // /session/end a second time. endSession re-sets the latch (no-op)
      // when it finally runs from the modal handler.
      finishedManuallyRef.current = true;
      // Open the post-read gate. The handler will call endSession.
      setPostReadAdOpen(true);
    } else {
      // No active session — just return home so the user isn't stuck.
      finishedManuallyRef.current = true;
      router.replace('/(tabs)');
    }
  };

  const onPostReadAdClaim = async (revenueUsd: number) => {
    // User watched the ad — close the modal, credit the ad reward, and
    // run the close-out: /session/end stages pending_points; the auto-
    // claim inside endSession credits it (or not, if 0); /progress/finish
    // advances the slice pointer; navigate to book detail.
    setPostReadAdOpen(false);
    // Fire the credit before endSession so the wallet bump lands on the
    // book detail screen the user is about to land on. The credit
    // handler invalidates ['me'] which triggers a refetch on whatever
    // screen the user lands on next.
    await creditAdReward('post_read', revenueUsd);
    if (sessionIdRef.current) {
      await endSession(sessionIdRef.current);
    }
  };

  const onPostReadAdSkip = async () => {
    // User skipped the second ad — still close out the session, still
    // advance the slice pointer, but forfeit the points (we don't
    // /session/claim, so pending_points stays staged and unclaimed on
    // the row). Same forfeit model as before, just initiated by the
    // modal being dismissed without watching.
    setPostReadAdOpen(false);
    if (sessionIdRef.current) {
      await endSession(sessionIdRef.current);
    }
  };

  // User taps the inline Finish button at the end of the slice. One-shot
  // via finishFiredRef — a double-tap can't fire twice.
  const onFinishTap = async () => {
    if (finishFiredRef.current) return;
    finishFiredRef.current = true;
    await triggerFinish();
  };

  const formatTime = (totalSeconds: number) => {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const potentialPoints = Math.max(0, Math.floor(elapsedSeconds / 600) * 5);

  // Pre-read gate handlers.
    // Credit the user's wallet based on the revenue this single ad
  // impression earned. Called from the ad-modal's onClaim with the
  // synthetic USD revenue the modal generated. Invalidates ['me'] so
  // the home chip + wallet tab reflect the new balance immediately.
  //
  // Network errors here are non-fatal: the modal close-out flow
  // (startSession, endSession) runs regardless. The user gets their
  // read reward even if the ad-credit call fails — we just log and
  // move on, rather than trapping them on a screen because an ad
  // network was down.
  const creditAdReward = async (adUnit: 'pre_read' | 'post_read', revenueUsd: number) => {
    // Unique per impression. Phase 2 swaps this for the real SDK's
    // transaction id (AdMob's onAdPaid callback, AppLovin's postback).
    // For now a timestamp + ad_unit + session_id is unique within a
    // single user and idempotent against accidental replay.
    const transactionId = `mock-${sessionIdRef.current ?? 0}-${adUnit}-${Date.now()}`;
    try {
      const res = await apiFetch('/api/v1/ads/credit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ad_unit: adUnit,
          provider: 'mock',
          revenue_usd: revenueUsd,
          transaction_id: transactionId,
        }),
      });
      const ct = res.headers.get('content-type') ?? '';
      if (!ct.includes('application/json')) {
        console.warn('Ad credit non-JSON response', res.status);
        return;
      }
      const json = await res.json();
      // Refresh the home chip + wallet tab with the server's authoritative balance.
      queryClient.invalidateQueries({ queryKey: ['me'] });
      queryClient.invalidateQueries({ queryKey: ['wallet'] });
      if (json.credit_status === 'credited') {
        console.info(
          `Ad credit: +${json.points_credited} pts (rate ₦${json.fx_rate_used.toFixed(2)}/$1, ` +
          `user share ₦${json.user_share_ngn.toFixed(4)}, balance ${json.new_balance})`,
        );
      }
    } catch (e) {
      console.warn('Ad credit failed (non-fatal)', e);
    }
  };

  const onPreReadClaim = async (revenueUsd: number) => {
    setPreReadOpen(false);
    // Fire the credit call in parallel with startSession — the credit
    // doesn't depend on the session id, and the user shouldn't have to
    // wait for two sequential network calls to start reading.
    void creditAdReward('pre_read', revenueUsd);
    try {
      await startSession();
    } catch (e) {
      console.error('Start session failed', e);
      router.replace('/(tabs)');
    }
  };

  const onPreReadSkip = () => {
    setPreReadOpen(false);
    router.replace('/(tabs)');
  };

  if (loading) {
    return (
      <View style={[styles.center, { backgroundColor: tokens.paper }]}>
        <Text style={{ color: tokens.ink }}>Loading...</Text>
      </View>
    );
  }

  if (!content) {
    return (
      <View style={[styles.center, { backgroundColor: tokens.paper }]}>
        <Text style={{ color: tokens.ink }}>Content not found</Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: tokens.paper }]} testID="reader-screen">
      <View style={[styles.header, { borderBottomColor: tokens.border }]}>
        <Text style={[styles.title, { color: tokens.ink }]}>{content.title}</Text>
        <Text style={[styles.meta, { color: tokens.inkMuted }]}>
          {content.author || 'Unknown'} • {content.estimated_read_minutes} min read
        </Text>
        <View style={styles.timerRow}>
          <Text style={[styles.status, { color: tokens.mint }, paused && { color: tokens.signal }]}>
            {sessionId ? (paused ? '⏸ Paused' : '✅ Active') : '⏳ Waiting'}
          </Text>
          <Text style={[styles.timerText, { color: tokens.ink }]}>{formatTime(elapsedSeconds)}</Text>
          <Text style={[styles.pointsText, { color: tokens.mint }]}>+{potentialPoints} pts</Text>
        </View>
      </View>

      <ScrollView
        ref={scrollRef}
        style={styles.scroll}
        onScroll={handleScroll}
        scrollEventThrottle={200}
      >
        <Text style={[styles.body, { color: tokens.ink }]}>
          {content.body_text || 'No content available.'}
        </Text>
        {/* Inline end-of-slice footer. The Finish button only appears once
            1 minute has elapsed on the session timer (the "1 minute" gate
            that fires the reward prompt). Before that, the user is meant
            to keep reading — we show only a subtle hint at the bottom. */}
        <View style={styles.endFooter}>
          <View style={[styles.endDivider, { backgroundColor: tokens.border }]} />
          {elapsedSeconds >= 60 ? (
            <>
              <Text style={[styles.endLabel, { color: tokens.inkMuted }]}>
                1 minute reached — ready when you are
              </Text>
              <TouchableOpacity
                onPress={onFinishTap}
                disabled={!sessionId || finishFiredRef.current}
                accessibilityRole="button"
                accessibilityLabel="Finish this slice and claim points"
                activeOpacity={0.85}
                style={[
                  styles.finishBtn,
                  { backgroundColor: tokens.mint },
                  (!sessionId || finishFiredRef.current) && {
                    backgroundColor: tokens.border,
                  },
                ]}
              >
                <Text style={styles.finishBtnText}>
                  {finishFiredRef.current ? 'Finishing…' : 'Finish & claim'}
                </Text>
              </TouchableOpacity>
            </>
          ) : (
            <Text style={[styles.endLabel, { color: tokens.inkMuted }]}>
              Keep reading — finish unlocks at 1 min
            </Text>
          )}
        </View>
        <View style={{ height: 40 }} />
      </ScrollView>

      <MockAdModal
        visible={preReadOpen}
        eyebrow="Sponsored"
        title="Watch a short ad to earn from this read"
        body="A quick ad unlocks the timer. You'll earn points based on how long you read."
        claimLabel="Watch ad & start"
        durationSeconds={30}
        provider="mock"
        onClaim={onPreReadClaim}
        onSkip={onPreReadSkip}
      />

      {/* Post-read gate (the second ad). Sits BEFORE /session/end: the
          user watched the timer run for 1 min, tapped Finish, and now
          this ad is the close-out. Watching → end → auto-claim →
          progress → navigate. Skipping → end (still advances the slice
          pointer) but no claim is filed, so the user forfeits the
          pending points. Either path returns them to the book detail. */}
      <MockAdModal
        visible={postReadAdOpen}
        eyebrow="Sponsored"
        title="One more ad to wrap up"
        body="Watch a short ad to lock in your points for this read. Skip forfeits the reward but still saves your progress."
        claimLabel="Watch ad & finish"
        skipLabel="Skip & forfeit"
        durationSeconds={30}
        provider="mock"
        onClaim={onPostReadAdClaim}
        onSkip={onPostReadAdSkip}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { padding: 16, borderBottomWidth: 1 },
  title: { fontSize: 20, fontWeight: 'bold', marginBottom: 4 },
  meta: { fontSize: 13, marginBottom: 8 },
  timerRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  status: { fontSize: 13, fontWeight: '500' },
  paused: {},
  timerText: {
    fontSize: 15,
    fontWeight: '600',
    fontVariant: Platform.OS === 'ios' ? ['tabular-nums'] : undefined,
  },
  pointsText: { fontSize: 14, fontWeight: '600' },
  scroll: { flex: 1, padding: 16 },
  body: { fontSize: 16, lineHeight: 24 },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modalBox: { padding: 24, borderRadius: 12, width: '100%', gap: 12 },
  modalTitle: { fontSize: 18, fontWeight: 'bold' },
  modalText: { fontSize: 14 },
  // Inline end-of-slice footer. Sits in document flow at the natural end
  // of the body, so it never overlays any other content.
  endFooter: {
    marginTop: 32,
    alignItems: 'center',
    gap: 12,
  },
  endDivider: { width: 48, height: 2, borderRadius: 1 },
  endLabel: {
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 0.4,
    textTransform: 'uppercase',
  },
  finishBtn: {
    paddingHorizontal: 28,
    paddingVertical: 14,
    borderRadius: 999,
    minWidth: 220,
    alignItems: 'center',
  },
  finishBtnDisabled: {},
  finishBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});