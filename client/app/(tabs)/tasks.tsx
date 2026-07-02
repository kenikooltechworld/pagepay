import { View, Text, StyleSheet, FlatList, TouchableOpacity, RefreshControl, ActivityIndicator } from 'react-native';
import { useState, useCallback } from 'react';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Ionicons } from '@expo/vector-icons';
import { fetchTasks, type Task } from '@/src/features/tasks/api';

export default function TasksScreen() {
  const [refreshing, setRefreshing] = useState(false);

  const { data: tasksData, isLoading, refetch } = useQuery({
    queryKey: ['tasks'],
    queryFn: fetchTasks,
  });

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  const getPlatformIcon = (platform: string): any => {
    const platformLower = platform.toLowerCase();
    switch (platformLower) {
      case 'twitter':
      case 'x':
        return 'logo-twitter';
      case 'instagram':
        return 'logo-instagram';
      case 'tiktok':
        return 'logo-tiktok';
      case 'youtube':
        return 'logo-youtube';
      case 'facebook':
        return 'logo-facebook';
      case 'linkedin':
        return 'logo-linkedin';
      case 'website':
        return 'globe-outline';
      case 'app':
        return 'phone-portrait-outline';
      default:
        return 'briefcase-outline';
    }
  };

  const renderTask = ({ item }: { item: Task }) => {
    const netReward = Math.floor(item.reward_amount * 0.85); // After 15% platform fee
    const remaining = item.max_completions - item.completed_count;
    
    return (
      <TouchableOpacity
        style={styles.taskCard}
        onPress={() => router.push(`/tasks/${item.id}`)}
      >
        <View style={styles.taskHeader}>
          <View style={styles.taskTypeBadge}>
            <Text style={styles.taskTypeBadgeText}>{item.task_type.replace('_', ' ')}</Text>
          </View>
          <View style={styles.rewardBadge}>
            <Text style={styles.rewardText}>₦{(netReward / 100).toFixed(2)}</Text>
          </View>
        </View>

        <Text style={styles.taskTitle} numberOfLines={2}>
          {item.title}
        </Text>

        <Text style={styles.taskDescription} numberOfLines={2}>
          {item.description}
        </Text>

        <View style={styles.taskFooter}>
          <View style={styles.taskMeta}>
            <Ionicons name={getPlatformIcon(item.platform)} size={14} color="#666" />
            <Text style={styles.taskMetaText}>{item.platform}</Text>
          </View>

          <View style={styles.taskMeta}>
            <Ionicons name="people-outline" size={14} color="#666" />
            <Text style={styles.taskMetaText}>{remaining} left</Text>
          </View>

          <View style={styles.taskMeta}>
            <Ionicons name="time-outline" size={14} color="#666" />
            <Text style={styles.taskMetaText}>
              {new Date(item.expires_at).toLocaleDateString()}
            </Text>
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#6C5CE7" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Available Tasks</Text>
        <TouchableOpacity onPress={() => router.push('/tasks/profile')}>
          <Ionicons name="stats-chart" size={24} color="#6C5CE7" />
        </TouchableOpacity>
      </View>

      <FlatList
        data={tasksData?.items || []}
        renderItem={renderTask}
        keyExtractor={(item) => item.id.toString()}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="briefcase-outline" size={64} color="#ccc" />
            <Text style={styles.emptyText}>No tasks available</Text>
            <Text style={styles.emptySubtext}>Check back later for new opportunities</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  listContent: {
    padding: 16,
  },
  taskCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  taskHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  taskTypeBadge: {
    backgroundColor: '#6C5CE7',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  taskTypeBadgeText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  rewardBadge: {
    backgroundColor: '#00B894',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  rewardText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: 'bold',
  },
  taskTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
  },
  taskDescription: {
    fontSize: 14,
    color: '#666',
    lineHeight: 20,
    marginBottom: 12,
  },
  taskFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  taskMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  taskMetaText: {
    fontSize: 12,
    color: '#666',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginTop: 16,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#666',
    marginTop: 8,
  },
});
