import { View, Text, StyleSheet, ScrollView, TextInput, TouchableOpacity, Alert, ActivityIndicator } from 'react-native';
import { useState } from 'react';
import { router } from 'expo-router';
import { useMutation } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import { createTask, publishTask } from '@/src/features/sponsor/api';

const PLATFORMS = ['twitter', 'instagram', 'tiktok', 'youtube', 'facebook', 'linkedin', 'website', 'app'];
const TASK_TYPES = ['follow', 'like', 'subscribe', 'retweet', 'comment', 'share', 'visit', 'signup', 'download', 'review'];

export default function CreateTaskScreen() {
  const { t } = useTranslation();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState('');
  const [platform, setPlatform] = useState('twitter');
  const [taskType, setTaskType] = useState('follow');
  const [targetUrl, setTargetUrl] = useState('');
  const [rewardKobo, setRewardKobo] = useState('5000');
  const [maxCompletions, setMaxCompletions] = useState('100');

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: async (data) => {
      Alert.alert(t('sponsor_create_task.success_title'), t('sponsor_create_task.publish_prompt'), [
        { text: t('sponsor_create_task.later_button'), onPress: () => router.back() },
        {
          text: t('sponsor_create_task.publish_button'),
          onPress: async () => {
            try {
              await publishTask(data.id);
              Alert.alert(t('sponsor_create_task.published_title'), t('sponsor_create_task.published_message'), [
                { text: 'OK', onPress: () => router.back() }
              ]);
            } catch (error: any) {
              Alert.alert(t('sponsor_create_task.errors.publish_failed'), error.message);
            }
          },
        },
      ]);
    },
    onError: (error: any) => {
      Alert.alert(t('sponsor_create_task.errors.creation_failed'), error.message);
    },
  });

  const handleSubmit = () => {
    if (!title || !description || !instructions) {
      Alert.alert(t('sponsor_create_task.errors.missing_fields'));
      return;
    }

    const reward = parseInt(rewardKobo);
    const max = parseInt(maxCompletions);

    if (isNaN(reward) || reward < 1000) {
      Alert.alert(t('sponsor_create_task.errors.invalid_reward'));
      return;
    }

    if (isNaN(max) || max < 1) {
      Alert.alert(t('sponsor_create_task.errors.invalid_completions'));
      return;
    }

    createMutation.mutate({
      title,
      description,
      instructions,
      task_type: taskType,
      platform,
      category: 'social_media',
      target_url: targetUrl || undefined,
      proof_type: 'screenshot',
      reward_amount_kobo: reward,
      max_completions: max,
      expires_in_days: 7,
      ai_verification_enabled: true,
    });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contentContainer}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#333" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{t('sponsor_create_task.title')}</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>{t('sponsor_create_task.title_label')}</Text>
        <TextInput
          style={styles.input}
          placeholder={t('sponsor_create_task.title_placeholder')}
          value={title}
          onChangeText={setTitle}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>{t('sponsor_create_task.description_label')}</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder={t('sponsor_create_task.description_placeholder')}
          value={description}
          onChangeText={setDescription}
          multiline
          numberOfLines={3}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>{t('sponsor_create_task.instructions_label')}</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder={t('sponsor_create_task.instructions_placeholder')}
          value={instructions}
          onChangeText={setInstructions}
          multiline
          numberOfLines={3}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>{t('sponsor_create_task.platform_label')}</Text>
        <View style={styles.pillsContainer}>
          {PLATFORMS.map((p) => (
            <TouchableOpacity
              key={p}
              style={[styles.pill, platform === p && styles.pillActive]}
              onPress={() => setPlatform(p)}
            >
              <Text style={[styles.pillText, platform === p && styles.pillTextActive]}>
                {p}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>{t('sponsor_create_task.task_type_label')}</Text>
        <View style={styles.pillsContainer}>
          {TASK_TYPES.map((type) => (
            <TouchableOpacity
              key={type}
              style={[styles.pill, taskType === type && styles.pillActive]}
              onPress={() => setTaskType(type)}
            >
              <Text style={[styles.pillText, taskType === type && styles.pillTextActive]}>
                {type}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>{t('sponsor_create_task.target_url_label')}</Text>
        <TextInput
          style={styles.input}
          placeholder={t('sponsor_create_task.target_url_placeholder')}
          value={targetUrl}
          onChangeText={setTargetUrl}
          autoCapitalize="none"
        />
      </View>

      <View style={styles.row}>
        <View style={[styles.section, styles.halfWidth]}>
          <Text style={styles.label}>{t('sponsor_create_task.reward_label')}</Text>
          <TextInput
            style={styles.input}
            placeholder={t('sponsor_create_task.reward_placeholder')}
            value={(parseInt(rewardKobo) / 100).toFixed(2)}
            onChangeText={(val) => setRewardKobo((parseFloat(val) * 100).toString())}
            keyboardType="numeric"
          />
        </View>

        <View style={[styles.section, styles.halfWidth]}>
          <Text style={styles.label}>{t('sponsor_create_task.max_workers_label')}</Text>
          <TextInput
            style={styles.input}
            placeholder={t('sponsor_create_task.max_workers_placeholder')}
            value={maxCompletions}
            onChangeText={setMaxCompletions}
            keyboardType="numeric"
          />
        </View>
      </View>

      <View style={styles.costCard}>
        <Text style={styles.costLabel}>{t('sponsor_create_task.estimated_cost_label')}</Text>
        <Text style={styles.costValue}>
          ₦{((parseInt(rewardKobo) * parseInt(maxCompletions)) / 100).toFixed(2)}
        </Text>
        <Text style={styles.costNote}>{t('sponsor_create_task.platform_fee_note')}</Text>
      </View>

      <TouchableOpacity
        style={[styles.submitButton, createMutation.isPending && styles.submitButtonDisabled]}
        onPress={handleSubmit}
        disabled={createMutation.isPending}
      >
        {createMutation.isPending ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <>
            <Ionicons name="checkmark-circle" size={24} color="#fff" />
            <Text style={styles.submitButtonText}>{t('sponsor_create_task.submit_button')}</Text>
          </>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  contentContainer: {
    padding: 16,
    paddingBottom: 32,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 24,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#fff',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  section: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: '#333',
  },
  textArea: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  pillsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  pill: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  pillActive: {
    backgroundColor: '#6C5CE7',
    borderColor: '#6C5CE7',
  },
  pillText: {
    fontSize: 14,
    color: '#666',
    textTransform: 'capitalize',
  },
  pillTextActive: {
    color: '#fff',
    fontWeight: '600',
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  halfWidth: {
    flex: 1,
  },
  costCard: {
    backgroundColor: '#E3F2FD',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    marginBottom: 24,
  },
  costLabel: {
    fontSize: 14,
    color: '#666',
    marginBottom: 8,
  },
  costValue: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#6C5CE7',
    marginBottom: 4,
  },
  costNote: {
    fontSize: 12,
    color: '#666',
  },
  submitButton: {
    backgroundColor: '#6C5CE7',
    borderRadius: 12,
    padding: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    shadowColor: '#6C5CE7',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  submitButtonDisabled: {
    backgroundColor: '#ccc',
    shadowOpacity: 0,
    elevation: 0,
  },
  submitButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
});
