/**
 * 5-screen onboarding.
 *
 * Horizontal pager: a `ScrollView` with `pagingEnabled` and a snap
 * interval matching the screen width. The active dot updates on
 * scroll-end. The `Skip` button advances to the last screen; the
 * final `Get started` tap fires the confetti, persists the
 * `onboardingCompleted` flag, and routes to `/(auth)/login`.
 *
 * Battery: all hero continuous loops live inside the individual
 * hero components, which mount only when their parent screen
 * becomes active. `useFocusEffect` from `@react-navigation/native`
 * would be a future improvement to stop loops when this whole route
 * loses focus (e.g. user backgrounds the app during onboarding);
 * the initial version is acceptable because the loops are cheap
 * (≤8 floating tokens per hero).
 */
import { useCallback, useRef, useState } from 'react';
import {
  Dimensions,
  NativeScrollEvent,
  NativeSyntheticEvent,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { OnboardingScreen } from '@/components/onboarding/OnboardingScreen';
import { ConfettiBurst } from '@/components/onboarding/Confetti';
import { EarnHero } from '@/components/onboarding/heroes/EarnHero';
import { StudyHero } from '@/components/onboarding/heroes/StudyHero';
import { WalletHero } from '@/components/onboarding/heroes/WalletHero';
import { StreakHero } from '@/components/onboarding/heroes/StreakHero';
import { PremiumHero } from '@/components/onboarding/heroes/PremiumHero';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import {
  persistOnboardingCompleted,
  usePreferences,
} from '@/src/shared/lib/preferences';

const { width: SCREEN_W } = Dimensions.get('window');

const SCREENS = [
  {
    eyebrow: 'WELCOME TO PAGEPAY',
    headline: 'Earn while you read',
    body: 'Read books and articles. Earn points for every minute of verified reading time.',
    Hero: EarnHero,
  },
  {
    eyebrow: 'STUDY SMARTER',
    headline: 'Turn your syllabus into quizzes',
    body: 'Upload your course material. Our AI generates quizzes, flashcards, and practice questions in seconds.',
    Hero: StudyHero,
  },
  {
    eyebrow: 'REAL REWARDS',
    headline: 'Cash out or go premium',
    body: 'Convert your points to Naira via Flutterwave, or unlock premium for ad-free reading and 2× points.',
    Hero: WalletHero,
  },
  {
    eyebrow: 'DAILY STREAK',
    headline: 'Read every day, earn more',
    body: 'Build a 7-day streak. Unlock bonus point multipliers the longer you read in a row.',
    Hero: StreakHero,
  },
  {
    eyebrow: 'GO PREMIUM',
    headline: '2× points, zero ads',
    body: 'Unlock premium for ad-free reading, double your points, and get unlimited AI study material.',
    Hero: PremiumHero,
  },
] as const;

type ConfettiOrigin = { x: number; y: number } | null;

export default function Onboarding() {
  const router = useRouter();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const setOnboardingCompleted = usePreferences((s) => s.setOnboardingCompleted);

  const [active, setActive] = useState(0);
  const [confetti, setConfetti] = useState<ConfettiOrigin>(null);
  const scrollRef = useRef<ScrollView>(null);

  const goTo = useCallback(
    (index: number) => {
      const clamped = Math.max(0, Math.min(SCREENS.length - 1, index));
      scrollRef.current?.scrollTo({ x: clamped * SCREEN_W, animated: true });
      setActive(clamped);
    },
    [],
  );

  const handleScrollEnd = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      const i = Math.round(e.nativeEvent.contentOffset.x / SCREEN_W);
      setActive(i);
    },
    [],
  );

  const handlePrimary = useCallback(
    (origin: { x: number; y: number }) => {
      if (active < SCREENS.length - 1) {
        goTo(active + 1);
        return;
      }
      // Final screen: fire confetti from the tap point, persist the
      // flag, then route to /login once the burst has settled.
      setConfetti(origin);
    },
    [active, goTo],
  );

  const handleConfettiDone = useCallback(() => {
    setConfetti(null);
    setOnboardingCompleted(true);
    // Persist in the background — if it fails (rare) the in-memory
    // flag is still set and the user is routed correctly. The next
    // app launch will re-prompt onboarding, which is a tolerable
    // failure mode (it's never destructive).
    void persistOnboardingCompleted(true);
    router.replace('/(auth)/login');
  }, [router, setOnboardingCompleted]);

  return (
    <View style={[styles.root, { backgroundColor: tokens.paper }]}>
      <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
        <ScrollView
          ref={scrollRef}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          onMomentumScrollEnd={handleScrollEnd}
          style={styles.scroll}
        >
          {SCREENS.map((s, i) => {
            const Hero = s.Hero;
            return (
              <View key={i} style={[styles.page, { width: SCREEN_W }]}>
                <OnboardingScreen
                  eyebrow={s.eyebrow}
                  headline={s.headline}
                  body={s.body}
                  index={i}
                  total={SCREENS.length}
                  isLast={i === SCREENS.length - 1}
                  onSkip={() => goTo(SCREENS.length - 1)}
                  onPrimary={handlePrimary}
                >
                  <Hero />
                </OnboardingScreen>
              </View>
            );
          })}
        </ScrollView>
      </SafeAreaView>

      <ConfettiBurst origin={confetti} onComplete={handleConfettiDone} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  safe: { flex: 1 },
  scroll: { flex: 1 },
  page: { flex: 1 },
});
