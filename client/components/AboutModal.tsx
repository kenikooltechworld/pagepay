import Constants from 'expo-constants';
import {
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type AboutModalProps = {
  visible: boolean;
  onClose: () => void;
};

/**
 * Read-only "About this app" modal. Shows the running version (from
 * expo-constants), the platform, and a one-paragraph mission blurb.
 * Version comes from `expo-constants.app.config.ios.version` /
 * `android.versionCode` — whichever Expo exposes.
 */
export function AboutModal({ visible, onClose }: AboutModalProps) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const version =
    // expo-constants 1.x exposes the resolved config under
    // `expoConfig.version`; fall back to `manifest.version` so older
    // SDK builds still report something.
    (Constants.expoConfig?.version as string | undefined) ||
    ((Constants.manifest as { version?: string } | undefined)?.version as string | undefined) ||
    '1.0.0';
  const platformLabel =
    Platform.OS === 'ios' ? 'iOS' : Platform.OS === 'android' ? 'Android' : Platform.OS;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <View style={[styles.sheet, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
          <View style={styles.headerRow}>
            <Text style={[styles.title, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
              About PagePay
            </Text>
            <Pressable
              onPress={onClose}
              hitSlop={12}
              accessibilityRole="button"
              accessibilityLabel="Close"
            >
              <Text style={[styles.close, { color: tokens.inkMuted }]}>Done</Text>
            </Pressable>
          </View>

          <View style={styles.body}>
            <View style={styles.brandRow}>
              <View>
                <Text style={[styles.wordmark, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
                  PagePay
                </Text>
              </View>
              <Text style={[styles.tagline, { color: tokens.mint }]}>Read. Earn. Repeat.</Text>
            </View>

            <Text style={[styles.mission, { color: tokens.inkMuted }]}>
              PagePay turns the time you spend reading into points you can
              actually spend. Built for Nigeria first — Nigerian books,
              Nigerian banks, and rewards that actually feel like money.
            </Text>

            <View style={[styles.metaRow, { borderTopColor: tokens.border, borderBottomColor: tokens.border }]}>
              <Meta label="Version" value={version} tokens={tokens} />
              <View style={[styles.divider, { backgroundColor: tokens.border }]} />
              <Meta label="Platform" value={platformLabel} tokens={tokens} />
            </View>

            <View style={styles.linkRow}>
              <Text style={[styles.linkHint, { color: tokens.inkMuted }]}>
                Terms of service and privacy policy will appear here once
                published. Placeholder for v1.
              </Text>
            </View>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function Meta({
  label,
  value,
  tokens,
}: {
  label: string;
  value: string;
  tokens: (typeof PagePay)['light'] | (typeof PagePay)['dark'];
}) {
  return (
    <View style={styles.meta}>
      <Text style={[styles.metaLabel, { color: tokens.inkMuted }]}>{label}</Text>
      <Text style={[styles.metaValue, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderLeftWidth: StyleSheet.hairlineWidth,
    borderRightWidth: StyleSheet.hairlineWidth,
    paddingTop: 18,
    paddingHorizontal: 20,
    paddingBottom: 32,
    maxHeight: '80%',
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  title: {
    fontSize: 20,
    letterSpacing: 0.1,
  },
  close: {
    fontSize: 15,
    fontWeight: '600',
  },
  body: {
    gap: 18,
  },
  brandRow: {
    alignItems: 'center',
    gap: 6,
    paddingVertical: 6,
  },
  wordmark: {
    fontSize: 28,
    letterSpacing: 0.5,
    textAlign: 'center',
  },
  tagline: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 1.4,
  },
  mission: {
    fontSize: 14,
    lineHeight: 21,
    textAlign: 'center',
    paddingHorizontal: 8,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  meta: {
    flex: 1,
    alignItems: 'center',
    gap: 4,
  },
  metaLabel: {
    fontSize: 11,
    letterSpacing: 1.0,
    fontWeight: '600',
  },
  metaValue: {
    fontSize: 16,
  },
  divider: {
    width: StyleSheet.hairlineWidth,
    height: 32,
  },
  linkRow: {
    paddingVertical: 4,
  },
  linkHint: {
    fontSize: 13,
    lineHeight: 19,
    textAlign: 'center',
  },
});
