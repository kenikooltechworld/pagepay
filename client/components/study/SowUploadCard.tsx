import { useState } from 'react';
import { StyleSheet, Text, TextInput, TouchableOpacity, View, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { PrimaryButton } from '@/components/PrimaryButton';

type SowUploadCardProps = {
  uploading: boolean;
  uploadProgress?: number;
  onUploadText: (text: string) => Promise<void>;
  onUploadImage: () => Promise<void>;
  onUploadDocument: () => Promise<void>;
};

export function SowUploadCard({
  uploading,
  uploadProgress,
  onUploadText,
  onUploadImage,
  onUploadDocument,
}: SowUploadCardProps) {
  const [text, setText] = useState('');
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const handleTextSubmit = async () => {
    if (!text.trim() || uploading) return;
    try {
      await onUploadText(text.trim());
      setText('');
    } catch {
      // error handled by parent
    }
  };

  return (
    <View style={[styles.card, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
      <View style={styles.headerRow}>
        <Ionicons name="cloud-upload-outline" size={22} color={tokens.mint} />
        <Text style={[styles.title, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
          Upload Scheme of Work
        </Text>
      </View>
      <Text style={[styles.subtitle, { color: tokens.inkMuted }]}>
        Paste text, upload a photo, or attach a PDF. AI will structure it into topics and generate study assets.
      </Text>

      <TextInput
        style={[styles.textInput, { backgroundColor: tokens.paper, borderColor: tokens.border, color: tokens.ink }]}
        placeholder="Paste your SOW / syllabus text here..."
        placeholderTextColor={tokens.inkMuted}
        multiline
        numberOfLines={4}
        value={text}
        onChangeText={setText}
        editable={!uploading}
        textAlignVertical="top"
      />

      {uploading && (
        <View style={styles.progressRow}>
          <ActivityIndicator size="small" color={tokens.mint} />
          <Text style={[styles.progressText, { color: tokens.inkMuted }]}>
            Processing{uploadProgress !== undefined && uploadProgress < 100 ? ` ${uploadProgress}%` : '...'}
          </Text>
        </View>
      )}

      <View style={styles.buttonRow}>
        <PrimaryButton
          title={uploading ? 'Processing...' : 'Upload Text'}
          onPress={handleTextSubmit}
          loading={uploading}
          disabled={!text.trim() || uploading}
        />
        <TouchableOpacity
          onPress={onUploadDocument}
          disabled={uploading}
          style={[styles.iconBtn, { borderColor: tokens.border }]}
          activeOpacity={0.7}
        >
          <Ionicons name="document" size={20} color={tokens.mint} />
        </TouchableOpacity>
        <TouchableOpacity
          onPress={onUploadImage}
          disabled={uploading}
          style={[styles.iconBtn, { borderColor: tokens.border }]}
          activeOpacity={0.7}
        >
          <Ionicons name="camera" size={20} color={tokens.mint} />
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 20,
    gap: 12,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  title: {
    fontSize: 18,
    letterSpacing: -0.3,
  },
  subtitle: {
    fontSize: 13,
    lineHeight: 18,
  },
  textInput: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    fontSize: 14,
    minHeight: 100,
    fontFamily: 'normal',
  },
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 4,
  },
  progressText: {
    fontSize: 13,
  },
  buttonRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  iconBtn: {
    width: 52,
    height: 52,
    borderRadius: 14,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
