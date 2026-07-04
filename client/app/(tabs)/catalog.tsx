import { useCallback, useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ActivityIndicator,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';

import { apiFetch } from '@/src/shared/api/client';
import { useCatalogFilter } from '@/src/shared/lib/catalog-filter';
import { ContentCard, ContentItem } from '@/components/ContentCard';
import { SkeletonContentCard } from '@/components/skeletons';
import { CategoryChip } from '@/components/CategoryChip';
import { NativeAdBanner } from '@/components/ads/NativeAdBanner';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

const FILTERS = ['All', 'Fiction', 'Classics', 'News', 'Study'] as const;

// Anonymous-browse fallback for the per-user sponsored shuffle. Any
// fixed value works — the shuffle is stable per-id so the same
// anonymous user sees the same ad order between page refreshes.
// 0 is reserved server-side (no user has id=0) so it's a safe sentinel.
const ANONYMOUS_USER_ID = 0;

export default function CatalogScreen() {
  const router = useRouter();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const queryClient = useQueryClient();

  // The store is the source of truth for category. Home writes to it when the
  // user taps a "Browse" chip, and we read it here so the screen comes up
  // already filtered.
  const storeCategory = useCatalogFilter((s) => s.category);
  const setStoreCategory = useCatalogFilter((s) => s.setCategory);

  const [refreshing, setRefreshing] = useState(false);

  // Fetch ad config for native unit
  const [nativeAdUnit, setNativeAdUnit] = useState('');
  const { data: adConfig } = useQuery({
    queryKey: ['ads-config'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/config/ads?env=dev');
      if (!res.ok) return {};
      return (await res.json()) as Record<string, string>;
    },
  });

  useEffect(() => {
    if (adConfig) {
      const platform = Platform.OS;
      const unitKey = platform === 'android' ? 'in_feed_android' : 'in_feed_ios';
      setNativeAdUnit(adConfig[unitKey] || '');
    }
  }, [adConfig]);

  // Phase 2: switch the catalog list source to `/content/feed/:user_id`
  // so the in-feed sponsored rotation lands every 4th item per the
  // spec. The legacy `/content/catalog` endpoint is kept (admin + raw
  // browse) but the user-facing tab now goes through the feed.
  //
  // We need the user_id for the per-user ad shuffle. Auth'd users
  // pass their real id (read from the `me` cache that the layout
  // populates on app start). Anonymous browsers fall back to a
  // fixed id so the shuffle is stable across refreshes.
  const meQuery = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const token = await (await import('@/src/shared/lib/storage')).getToken();
      if (!token) return null;
      const res = await apiFetch('/api/v1/auth/me');
      if (!res.ok) return null;
      return (await res.json()) as { id: number };
    },
    staleTime: 5 * 60 * 1000,
  });
  const userId = meQuery.data?.id ?? ANONYMOUS_USER_ID;

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['feed', userId, storeCategory],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (storeCategory) params.set('category', storeCategory);
      params.set('limit', '50');
      const url = `/api/v1/content/feed/${userId}?${params.toString()}`;
      const res = await apiFetch(url);
      if (!res.ok) throw new Error('Failed to load catalog');
      return (await res.json()) as ContentItem[];
    },
  });

  // On-demand refresh: import a fresh page of Gutendex and re-slice the
  // entire catalog. Used by the empty-state CTA — when the user has
  // finished everything we have, this is the way to get more.
  const refreshMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch('/api/v1/content/refresh', { method: 'POST' });
      if (!res.ok) throw new Error('Refresh failed');
      return (await res.json()) as { imported: number; resliced: { children_added: number; parents_resliced: number } };
    },
    onSuccess: () => {
      // Invalidate every catalog-shaped query so the new books show up.
      queryClient.invalidateQueries({ queryKey: ['catalog'] });
      queryClient.invalidateQueries({ queryKey: ['book'] });
      queryClient.invalidateQueries({ queryKey: ['feed'] });
    },
  });

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  const onClearFilter = useCallback(() => {
    setStoreCategory(null);
  }, [setStoreCategory]);

  const items = data ?? [];
  const isInitialLoad = isLoading && !refreshing && items.length === 0;

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: tokens.paper }]}>
      <View style={styles.header}>
        <Text
          style={[
            styles.headline,
            { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' },
          ]}
        >
          Catalog
        </Text>
        <Text style={[styles.subline, { color: tokens.inkMuted }]}>
          {storeCategory ? `Filtered: ${storeCategory}` : 'Every read pays. Pick one.'}
        </Text>
      </View>

      <View style={styles.filterRow}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ gap: 8, paddingHorizontal: 16 }}
        >
          {FILTERS.map((f) => {
            const value = f === 'All' ? null : f;
            return (
              <CategoryChip
                key={f}
                label={f}
                selected={storeCategory === value}
                onPress={() => setStoreCategory(value)}
              />
            );
          })}
        </ScrollView>
      </View>

      {storeCategory ? (
        <TouchableOpacity
          onPress={onClearFilter}
          accessibilityRole="button"
          accessibilityLabel="Clear category filter"
          style={styles.clearRow}
          hitSlop={6}
        >
          <Ionicons name="close-circle" size={14} color={tokens.inkMuted} />
          <Text style={[styles.clearText, { color: tokens.inkMuted }]}>
            Clear filter
          </Text>
        </TouchableOpacity>
      ) : null}

      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={tokens.mint}
          />
        }
      >
        {isInitialLoad ? (
          <View style={styles.list}>
            {Array.from({ length: 3 }).map((_, i) => (
              <SkeletonContentCard key={i} />
            ))}
          </View>
        ) : isError ? (
          <View style={[styles.stateBlock, { borderColor: tokens.signal }]}>
            <Ionicons name="cloud-offline-outline" size={20} color={tokens.signal} />
            <Text style={[styles.stateText, { color: tokens.signal }]}>
              Couldn&apos;t load the catalog.
            </Text>
            <TouchableOpacity
              onPress={() => refetch()}
              style={[styles.retry, { borderColor: tokens.signal }]}
              activeOpacity={0.7}
            >
              <Text style={[styles.retryText, { color: tokens.signal }]}>Try again</Text>
            </TouchableOpacity>
          </View>
        ) : items.length === 0 ? (
          <View style={[styles.stateBlock, { borderColor: tokens.border }]}>
            <Ionicons name="library-outline" size={28} color={tokens.mint} />
            <Text style={[styles.stateText, { color: tokens.inkMuted }]}>
              {storeCategory
                ? `No reads in "${storeCategory}" yet.`
                : "You've finished everything we have. Pull more?"}
            </Text>
            <TouchableOpacity
              onPress={() => refreshMutation.mutate()}
              disabled={refreshMutation.isPending}
              accessibilityRole="button"
              accessibilityLabel="Pull fresh books from the catalog"
              activeOpacity={0.9}
              style={[
                styles.refreshBtn,
                {
                  backgroundColor: refreshMutation.isPending ? tokens.border : tokens.mint,
                },
              ]}
            >
              {refreshMutation.isPending ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.refreshBtnText}>
                  {storeCategory ? 'Pull more books' : 'Refresh catalog'}
                </Text>
              )}
            </TouchableOpacity>
            {refreshMutation.isError ? (
              <Text style={[styles.stateText, { color: tokens.signal, fontSize: 12 }]}>
                Couldn&apos;t reach the catalog. Tap again.
              </Text>
            ) : null}
          </View>
        ) : (
          <View style={styles.list}>
            {items.map((item, index) => {
              // Inject native ad every 4th position
              const shouldShowAd = (index + 1) % 4 === 0 && nativeAdUnit;
              
              return (
                <View key={`catalog-${item.id}-${index}`}>
                  <ContentCard
                    item={item}
                    onPress={() => router.push(`/book/${item.id}` as never)}
                  />
                  {shouldShowAd && (
                    <NativeAdBanner
                      adUnit={nativeAdUnit}
                      sessionId={null}
                    />
                  )}
                </View>
              );
            })}
          </View>
        )}
        <View style={{ height: 24 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  header: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 16,
    gap: 4,
  },
  headline: {
    fontSize: 28,
    lineHeight: 34,
    letterSpacing: -0.5,
  },
  subline: {
    fontSize: 14,
    lineHeight: 20,
  },
  filterRow: {
    paddingVertical: 8,
  },
  clearRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 16,
    paddingTop: 4,
    paddingBottom: 4,
    alignSelf: 'flex-start',
  },
  clearText: {
    fontSize: 12,
    lineHeight: 16,
  },
  scroll: {
    paddingHorizontal: 16,
    paddingTop: 12,
    gap: 12,
  },
  list: {
    gap: 12,
  },
  stateBlock: {
    borderRadius: 14,
    borderWidth: 1,
    paddingVertical: 32,
    paddingHorizontal: 16,
    alignItems: 'center',
    gap: 8,
  },
  stateText: {
    fontSize: 13,
    lineHeight: 18,
    textAlign: 'center',
  },
  retry: {
    marginTop: 4,
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
  },
  retryText: {
    fontSize: 12,
    fontWeight: '600',
  },
  refreshBtn: {
    marginTop: 8,
    paddingHorizontal: 22,
    paddingVertical: 12,
    borderRadius: 999,
    minWidth: 180,
    alignItems: 'center',
    justifyContent: 'center',
  },
  refreshBtnText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
});
