import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';
import type { ConfigItem } from '@/lib/types';
import { useState } from 'react';
import { Card, Badge, Button, ShimmerLoader, Container } from '@/shared/components';
import { TopHeader } from '@/shared/components/TopHeader';
import { useLayoutContext } from '@/shared/components/Layout';

export function ConfigPage() {
  const { onMenuClick } = useLayoutContext();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editDesc, setEditDesc] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'config'],
    queryFn: async () => {
      const { data } = await adminApi.get<ConfigItem[]>('/admin/config');
      return data;
    },
    staleTime: 60_000,
  });

  const updateMutation = useMutation({
    mutationFn: async ({ key, value, description }: { key: string; value: string; description?: string }) => {
      await adminApi.put(`/admin/config/${encodeURIComponent(key)}`, { value, description });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'config'] });
      setEditingKey(null);
      setEditValue('');
      setEditDesc('');
    },
  });

  const queryClient = useQueryClient();

  const startEdit = (item: ConfigItem) => {
    setEditingKey(item.key);
    setEditValue(item.value);
    setEditDesc(item.description || '');
  };

  const saveEdit = (key: string) => {
    updateMutation.mutate({ key, value: editValue, description: editDesc || undefined });
  };

  return (
    <>
      <TopHeader title="System Configuration" subtitle="Manage app config and OTA settings" onMenuClick={onMenuClick} />
      <Container size="full">
        <Card>
        {isLoading && <div className="p-4 sm:p-6"><ShimmerLoader lines={5} /></div>}
        {error && <div className="p-4 sm:p-6 text-error">Failed to load config</div>}
        {data && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-bg-muted">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Key</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Value</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Environment</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Description</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.map((item) => (
                  <tr key={item.key} className="hover:bg-bg-hover">
                    <td className="px-4 py-3 text-sm font-mono text-text-main">{item.key}</td>
                    <td className="px-4 py-3 text-sm text-text-main">
                      {editingKey === item.key ? (
                        <input value={editValue} onChange={(e) => setEditValue(e.target.value)} className="w-full rounded-lg border border-border bg-bg-card px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" />
                      ) : (
                        item.value
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-text-main"><Badge variant={item.environment === 'prod' ? 'success' : 'info'}>{item.environment}</Badge></td>
                    <td className="px-4 py-3 text-sm text-text-main">
                      {editingKey === item.key ? (
                        <input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} className="w-full rounded-lg border border-border bg-bg-card px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" />
                      ) : (
                        item.description || '-'
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-text-main">
                      {editingKey === item.key ? (
                        <div className="flex flex-col gap-2 sm:flex-row">
                          <Button size="sm" onClick={() => saveEdit(item.key)}>Save</Button>
                          <Button size="sm" variant="secondary" onClick={() => setEditingKey(null)}>Cancel</Button>
                        </div>
                      ) : (
                        <Button size="sm" variant="secondary" onClick={() => startEdit(item)}>Edit</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      </Container>
    </>
  );
}
