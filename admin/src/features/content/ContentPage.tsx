import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';
import type { ContentListResponse } from '@/lib/types';
import { Trash2 } from 'lucide-react';
import React, { useState } from 'react';
import { Card, Badge, Button, Pagination, ShimmerLoader, Container, Tooltip } from '@/shared/components';
import { TopHeader } from '@/shared/components/TopHeader';
import { useLayoutContext } from '@/shared/components/Layout';
import { Input } from '@/shared/components/Input';
import { Select } from '@/shared/components/Select';

export function ContentPage() {
  const { onMenuClick } = useLayoutContext();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin', 'content', { page, search, typeFilter }],
    queryFn: async () => {
      const { data } = await adminApi.get<ContentListResponse>('/admin/content', {
        params: { page, limit: 50, search, content_type: typeFilter },
      });
      return data;
    },
    staleTime: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      if (!confirm('Delete this content?')) return;
      await adminApi.delete(`/admin/content/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'content'] });
    },
  });

  const queryClient = useQueryClient();
  const totalPages = data ? Math.ceil(data.total / data.limit) : 0;

  return (
    <>
      <TopHeader title="Content" subtitle="Manage catalog content" onMenuClick={onMenuClick} />
      <Container size="full">
        <Card>
        <div className="border-b border-border px-4 py-4 sm:px-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
            <Input
              label="Search"
              placeholder="Title..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="lg:max-w-xs"
            />
            <Select
              label="Type"
              value={typeFilter}
              onChange={(value) => { setTypeFilter(value); setPage(1); }}
              options={[
                { value: '', label: 'All Types' },
                { value: 'book', label: 'Book' },
                { value: 'article', label: 'Article' },
                { value: 'news', label: 'News' },
              ]}
              className="lg:max-w-xs"
            />
          </div>
        </div>

        {isLoading && <div className="p-4 sm:p-6"><ShimmerLoader lines={5} /></div>}
        {error && <div className="p-4 sm:p-6 text-error">Failed to load content</div>}

        {data && (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-bg-muted">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">ID</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Title</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Type</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Category</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Author</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Created</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.items.map((item) => (
                    <tr key={item.id} className="hover:bg-bg-hover">
                      <td className="px-4 py-3 text-sm text-text-main">{item.id}</td>
                      <td className="px-4 py-3 text-sm text-text-main">{item.title}</td>
                      <td className="px-4 py-3 text-sm text-text-main">{item.content_type}</td>
                      <td className="px-4 py-3 text-sm text-text-main">{item.category}</td>
                      <td className="px-4 py-3 text-sm text-text-main">{item.author || '-'}</td>
                      <td className="px-4 py-3 text-sm text-text-main">{new Date(item.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-sm text-text-main">
                        <Tooltip content="Delete this content" position="top">
                          <Button size="sm" variant="danger" onClick={() => deleteMutation.mutate(item.id)}>
                            <Trash2 size={14} /> Delete
                          </Button>
                        </Tooltip>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-4 sm:p-6">
              <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
            </div>
          </>
        )}
      </Card>
      </Container>
    </>
  );
}
