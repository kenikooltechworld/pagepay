import { useCallback, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';

import { apiFetch } from '@/src/shared/api/client';
import { useMaterials, useUploadSow, useUploadSowImage, useUploadSowDocument, useClaimQuizBonus } from '@/src/features/study/hooks/use-study';
import { useImagePicker } from '@/src/shared/hooks/use-image-picker';
import { useDocumentPicker } from '@/src/shared/hooks/use-document-picker';
import { SowUploadCard } from '@/components/study/SowUploadCard';
import { AssetBrowser } from '@/components/study/AssetBrowser';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { PrimaryButton } from '@/components/PrimaryButton';

type AssetInfo = {
  id: number;
  type: string;
  points_to_unlock: number;
  created_at: string;
};

type MaterialDetail = {
  id: number;
  title: string;
  parsed_structure: Record<string, unknown> | null;
  assets: AssetInfo[];
  created_at: string;
};

export default function StudyScreen() {
  const router = useRouter();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const qc = useQueryClient();

  const materialsQ = useMaterials();
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null);
  const [selectedMaterial, setSelectedMaterial] = useState<MaterialDetail | null>(null);
  const [unlockedAssets, setUnlockedAssets] = useState<Record<number, unknown>>({});
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [bonusNotification, setBonusNotification] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | undefined>(undefined);

  const meQ = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/auth/me');
      if (!res.ok) throw new Error('Failed');
      return res.json() as Promise<{ points_balance: number }>;
    },
  });

  const uploadMutation = useUploadSow();
  const uploadImageMutation = useUploadSowImage();
  const uploadDocumentMutation = useUploadSowDocument();
  const { pickImage } = useImagePicker();
  const { pickDocument } = useDocumentPicker();
  const claimBonusMutation = useClaimQuizBonus();

  const handleUploadText = async (text: string) => {
    setError(null);
    setUploadProgress(undefined);
    const result = await uploadMutation.mutateAsync({ text });
    setSelectedMaterialId(result.material_id);
    const res = await apiFetch(`/api/v1/study/materials/${result.material_id}`);
    if (res.ok) {
      setSelectedMaterial(await res.json());
    }
    setUploadProgress(100);
    setTimeout(() => setUploadProgress(undefined), 2000);
  };

  const handleUploadImage = async () => {
    setError(null);
    setUploadProgress(undefined);
    const file = await pickImage();
    if (!file) return;
    const result = await uploadImageMutation.mutateAsync({ uri: file.uri, name: file.name, type: file.type });
    setSelectedMaterialId(result.material_id);
    const res = await apiFetch(`/api/v1/study/materials/${result.material_id}`);
    if (res.ok) {
      setSelectedMaterial(await res.json());
    }
    setUploadProgress(100);
    setTimeout(() => setUploadProgress(undefined), 2000);
  };

  const handleUploadDocument = async () => {
    setError(null);
    setUploadProgress(undefined);
    const file = await pickDocument();
    if (!file) return;
    const result = await uploadDocumentMutation.mutateAsync({ uri: file.uri, name: file.name, type: file.type });
    setSelectedMaterialId(result.material_id);
    const res = await apiFetch(`/api/v1/study/materials/${result.material_id}`);
    if (res.ok) {
      setSelectedMaterial(await res.json());
    }
    setUploadProgress(100);
    setTimeout(() => setUploadProgress(undefined), 2000);
  };

  const handleGenerateAsset = async (materialId: number, assetType: string, count = 5) => {
    setGenerating(true);
    setError(null);
    try {
      const res = await apiFetch('/api/v1/study/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ material_id: materialId, asset_type: assetType, count }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Generation failed');
      }
      const detailRes = await apiFetch(`/api/v1/study/materials/${materialId}`);
      if (detailRes.ok) {
        setSelectedMaterial(await detailRes.json());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setGenerating(false);
    }
  };

  const handleQuizComplete = async (assetId: number, score: number) => {
    try {
      const result = await claimBonusMutation.mutateAsync({ asset_id: assetId, score });
      if (result.bonus_awarded) {
        setBonusNotification(`+${result.bonus_points} pts! Score: ${score}%`);
        setTimeout(() => setBonusNotification(null), 4000);
      }
      qc.invalidateQueries({ queryKey: ['me'] });
    } catch {
      // silent fail — bonus is optional
    }
  };

  const handleUnlock = async (assetId: number, method: 'points' | 'ad') => {
    setError(null);
    const res = await apiFetch('/api/v1/study/unlock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ asset_id: assetId, method }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Unlock failed');
    }
    const data = await res.json();
    if (data.unlocked && data.content) {
      setUnlockedAssets((prev) => ({ ...prev, [assetId]: data.content }));
    }
    qc.invalidateQueries({ queryKey: ['me'] });
    return data;
  };

  const handleMaterialPress = async (materialId: number) => {
    setSelectedMaterialId(materialId);
    const res = await apiFetch(`/api/v1/study/materials/${materialId}`);
    if (res.ok) {
      setSelectedMaterial(await res.json());
    }
  };

  const handleBack = () => {
    setSelectedMaterialId(null);
    setSelectedMaterial(null);
  };

  const handleChatPress = (materialId: number) => {
    router.push(`/study/chat/${materialId}`);
  };

  const materials = materialsQ.data ?? [];
  const balance = meQ.data?.points_balance ?? 0;
  const isLoading = materialsQ.isLoading;

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: tokens.paper }}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl refreshing={materialsQ.isFetching} onRefresh={() => qc.invalidateQueries({ queryKey: ['study', 'materials'] })} tintColor={tokens.mint} />
        }
      >
        <View style={styles.header}>
          <Text style={[styles.headline, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
            {selectedMaterial ? selectedMaterial.title : 'Study'}
          </Text>
          {selectedMaterial && (
            <Text style={[styles.subline, { color: tokens.inkMuted }]}>
              {selectedMaterial.assets.length} assets generated
            </Text>
          )}
        </View>

        {error && (
          <View style={[styles.errorBanner, { backgroundColor: tokens.signalSoft, borderColor: tokens.signal }]}>
            <Ionicons name="alert-circle-outline" size={18} color={tokens.signal} />
            <Text style={[styles.errorText, { color: tokens.signal }]}>{error}</Text>
            <TouchableOpacity onPress={() => setError(null)} hitSlop={6}>
              <Ionicons name="close" size={16} color={tokens.signal} />
            </TouchableOpacity>
          </View>
        )}

        {bonusNotification && (
          <View style={[styles.bonusBanner, { backgroundColor: tokens.mintSoft, borderColor: tokens.mint }]}>
            <Ionicons name="trophy-outline" size={18} color={tokens.mint} />
            <Text style={[styles.bonusText, { color: tokens.mint }]}>{bonusNotification}</Text>
            <TouchableOpacity onPress={() => setBonusNotification(null)} hitSlop={6}>
              <Ionicons name="close" size={16} color={tokens.mint} />
            </TouchableOpacity>
          </View>
        )}

        {selectedMaterial ? (
          <View style={styles.detailView}>
            <View style={styles.detailActions}>
              <TouchableOpacity
                onPress={handleBack}
                style={[styles.backBtn, { borderColor: tokens.border }]}
                activeOpacity={0.7}
              >
                <Ionicons name="arrow-back" size={18} color={tokens.mint} />
                <Text style={[styles.backText, { color: tokens.mint }]}>All materials</Text>
              </TouchableOpacity>
              <View style={styles.chatBtn}>
                <PrimaryButton
                  title="Chat with AI"
                  onPress={() => handleChatPress(selectedMaterial.id)}
                />
              </View>
            </View>

            {selectedMaterial.parsed_structure && (
              <View style={[styles.outlineCard, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
                <Text style={[styles.outlineTitle, { color: tokens.ink }]}>Topics covered</Text>
                {Object.entries(selectedMaterial.parsed_structure as Record<string, unknown>).length > 0 && (
                  <View style={styles.outlineList}>
                    {((selectedMaterial.parsed_structure as Record<string, unknown>).topics as Array<Record<string, unknown>> | undefined) &&
                 Array.isArray((selectedMaterial.parsed_structure as Record<string, unknown>).topics) &&
                 ((selectedMaterial.parsed_structure as Record<string, unknown>).topics as Array<Record<string, unknown>>).map((topic: Record<string, unknown>, idx: number) => (
                      <View key={idx} style={styles.outlineItem}>
                        <View style={[styles.outlineDot, { backgroundColor: tokens.mint }]} />
                        <Text style={[styles.outlineText, { color: tokens.ink }]}>
                          {String(topic.name)}
                        </Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            )}

            <AssetBrowser
              assets={selectedMaterial.assets}
              userBalance={balance}
              onUnlock={handleUnlock}
              unlockedAssets={unlockedAssets}
              onQuizComplete={handleQuizComplete}
            />

            <View style={styles.generateRow}>
              <GenerateButton
                label="MCQs"
                icon="help-circle-outline"
                onPress={() => handleGenerateAsset(selectedMaterial.id, 'mcq', 5)}
                loading={generating}
                tokens={tokens}
              />
              <GenerateButton
                label="Flashcards"
                icon="albums-outline"
                onPress={() => handleGenerateAsset(selectedMaterial.id, 'flashcard', 8)}
                loading={generating}
                tokens={tokens}
              />
              <GenerateButton
                label="Essays"
                icon="document-text-outline"
                onPress={() => handleGenerateAsset(selectedMaterial.id, 'essay', 3)}
                loading={generating}
                tokens={tokens}
              />
            </View>
          </View>
        ) : (
          <View style={styles.listView}>
            <SowUploadCard
              uploading={uploadMutation.isPending || uploadImageMutation.isPending || uploadDocumentMutation.isPending}
              uploadProgress={uploadProgress}
              onUploadText={handleUploadText}
              onUploadImage={handleUploadImage}
              onUploadDocument={handleUploadDocument}
            />

            {isLoading ? (
              <View style={styles.stateBlock}>
                <ActivityIndicator color={tokens.mint} />
                <Text style={[styles.stateText, { color: tokens.inkMuted }]}>Loading materials...</Text>
              </View>
            ) : materials.length > 0 ? (
              <View style={styles.materialList}>
                <Text style={[styles.listTitle, { color: tokens.ink }]}>Your materials</Text>
                {materials.map((m) => (
                  <TouchableOpacity
                    key={m.id}
                    onPress={() => handleMaterialPress(m.id)}
                    activeOpacity={0.7}
                    style={[styles.materialCard, { backgroundColor: tokens.card, borderColor: tokens.border }]}
                  >
                    <View style={[styles.materialIcon, { backgroundColor: tokens.mintSoft }]}>
                      <Ionicons name="book-outline" size={20} color={tokens.mint} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.materialTitle, { color: tokens.ink }]} numberOfLines={1}>
                        {m.title}
                      </Text>
                      <Text style={[styles.materialMeta, { color: tokens.inkMuted }]}>
                        {m.asset_types.join(', ')} · {new Date(m.created_at).toLocaleDateString()}
                      </Text>
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={tokens.inkMuted} />
                  </TouchableOpacity>
                ))}
              </View>
            ) : (
              <View style={[styles.stateBlock, { borderColor: tokens.border }]}>
                <Ionicons name="school-outline" size={32} color={tokens.mint} />
                <Text style={[styles.stateText, { color: tokens.inkMuted }]}>
                  Upload your first scheme of work to get started.
                </Text>
              </View>
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function GenerateButton({
  label,
  icon,
  onPress,
  loading,
  tokens,
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  loading: boolean;
  tokens: (typeof PagePay)['light'];
}) {
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={loading}
      activeOpacity={0.7}
      style={[styles.genBtn, { borderColor: tokens.border, backgroundColor: tokens.paper }]}
    >
      <Ionicons name={icon} size={18} color={tokens.mint} />
      <Text style={[styles.genText, { color: tokens.ink }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: 16,
    paddingBottom: 48,
  },
  header: {
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
  listView: {
    gap: 20,
  },
  detailView: {
    gap: 16,
  },
  detailActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    borderWidth: 1,
  },
  backText: {
    fontSize: 13,
    fontWeight: '600',
  },
  chatBtn: {
    flex: 1,
  },
  outlineCard: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
    gap: 10,
  },
  outlineTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  outlineList: {
    gap: 6,
  },
  outlineItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  outlineDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  outlineText: {
    fontSize: 14,
    lineHeight: 18,
  },
  generateRow: {
    flexDirection: 'row',
    gap: 8,
  },
  genBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
  },
  genText: {
    fontSize: 13,
    fontWeight: '600',
  },
  materialList: {
    gap: 10,
  },
  listTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 4,
  },
  materialCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
  },
  materialIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  materialTitle: {
    fontSize: 15,
    fontWeight: '600',
    marginBottom: 2,
  },
  materialMeta: {
    fontSize: 12,
  },
  stateBlock: {
    borderRadius: 14,
    borderWidth: 1,
    paddingVertical: 32,
    alignItems: 'center',
    gap: 8,
  },
  stateText: {
    fontSize: 13,
    textAlign: 'center',
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  errorText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
  },
  bonusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  bonusText: {
    flex: 1,
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 18,
  },
});
