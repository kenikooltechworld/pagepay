import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';
import type { FraudFlagListResponse } from '@/lib/types';
import { useState } from 'react';
import { Card, Badge, ShimmerLoader, Container, Button, ConfirmModal, Tooltip } from '@/shared/components';
import { TopHeader } from '@/shared/components/TopHeader';
import { useLayoutContext } from '@/shared/components/Layout';
import { Select } from '@/shared/components/Select';
import { AlertCircle, Copy, Users, CheckCircle, XCircle } from 'lucide-react';

export function FraudPage() {
  const { onMenuClick } = useLayoutContext();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'sessions' | 'duplicates' | 'referrals'>('sessions');
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [ignoreModalOpen, setIgnoreModalOpen] = useState(false);
  const [selectedFlag, setSelectedFlag] = useState<number | null>(null);
  const [resolveNotes, setResolveNotes] = useState('');
  const [ignoreReason, setIgnoreReason] = useState('');

  const { data: sessionsData, isLoading: sessionsLoading, error: sessionsError } = useQuery({
    queryKey: ['admin', 'fraud', 'sessions', { severity, status }],
    queryFn: async () => {
      const { data } = await adminApi.get<FraudFlagListResponse>('/admin/fraud/sessions', {
        params: { severity, status, page: 1, limit: 50 },
      });
      return data;
    },
    enabled: activeTab === 'sessions',
    staleTime: 30_000,
  });

  const { data: duplicatesData, isLoading: duplicatesLoading, error: duplicatesError } = useQuery({
    queryKey: ['admin', 'fraud', 'duplicates'],
    queryFn: async () => {
      const { data } = await adminApi.get<FraudFlagListResponse>('/admin/fraud/duplicates');
      return data;
    },
    enabled: activeTab === 'duplicates',
    staleTime: 30_000,
  });

  const { data: referralsData, isLoading: referralsLoading, error: referralsError } = useQuery({
    queryKey: ['admin', 'fraud', 'referrals'],
    queryFn: async () => {
      const { data } = await adminApi.get<FraudFlagListResponse>('/admin/fraud/referrals');
      return data;
    },
    enabled: activeTab === 'referrals',
    staleTime: 30_000,
  });

  // Mutation for resolving fraud flags
  const resolveMutation = useMutation({
    mutationFn: async ({ flagId, notes }: { flagId: number; notes?: string }) => {
      const params = notes ? `?notes=${encodeURIComponent(notes)}` : '';
      await adminApi.post(`/fraud/${flagId}/resolve${params}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'fraud'] });
      setResolveModalOpen(false);
      setResolveNotes('');
      setSelectedFlag(null);
    },
  });

  // Mutation for ignoring fraud flags
  const ignoreMutation = useMutation({
    mutationFn: async ({ flagId, reason }: { flagId: number; reason: string }) => {
      await adminApi.post(`/fraud/${flagId}/ignore?reason=${encodeURIComponent(reason)}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'fraud'] });
      setIgnoreModalOpen(false);
      setIgnoreReason('');
      setSelectedFlag(null);
    },
  });

  const handleResolveClick = (flagId: number) => {
    setSelectedFlag(flagId);
    setResolveModalOpen(true);
  };

  const handleIgnoreClick = (flagId: number) => {
    setSelectedFlag(flagId);
    setIgnoreModalOpen(true);
  };

  const handleResolveConfirm = () => {
    if (selectedFlag) {
      resolveMutation.mutate({ flagId: selectedFlag, notes: resolveNotes });
    }
  };

  const handleIgnoreConfirm = () => {
    if (selectedFlag && ignoreReason.trim()) {
      ignoreMutation.mutate({ flagId: selectedFlag, reason: ignoreReason });
    }
  };

  return (
    <>
      <TopHeader title="Fraud Detection" subtitle="Review flagged sessions and abuse patterns" onMenuClick={onMenuClick} />
      <Container size="full">
        <Card>
        {/* Tabs */}
        <div className="flex gap-2 border-b border-border px-4 pt-4">
          <button
            onClick={() => setActiveTab('sessions')}
            className={`cursor-pointer px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'sessions'
                ? 'border-b-2 border-primary text-primary'
                : 'text-text-muted hover:text-text-main'
            }`}
          >
            <AlertCircle size={16} className="mr-1.5 inline" />
            Suspicious Sessions
          </button>
          <button
            onClick={() => setActiveTab('duplicates')}
            className={`cursor-pointer px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'duplicates'
                ? 'border-b-2 border-primary text-primary'
                : 'text-text-muted hover:text-text-main'
            }`}
          >
            <Copy size={16} className="mr-1.5 inline" />
            Duplicate Accounts
          </button>
          <button
            onClick={() => setActiveTab('referrals')}
            className={`cursor-pointer px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'referrals'
                ? 'border-b-2 border-primary text-primary'
                : 'text-text-muted hover:text-text-main'
            }`}
          >
            <Users size={16} className="mr-1.5 inline" />
            Referral Abuse
          </button>
        </div>

        {/* Filters (only for sessions tab) */}
        {activeTab === 'sessions' && (
          <div className="border-b border-border px-4 py-4 sm:px-6">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
              <Select
                label="Severity"
                value={severity}
                onChange={(value) => setSeverity(value)}
                options={[
                  { value: '', label: 'All Severity' },
                  { value: 'low', label: 'Low' },
                  { value: 'medium', label: 'Medium' },
                  { value: 'high', label: 'High' },
                ]}
                className="lg:max-w-xs"
              />
              <Select
                label="Status"
                value={status}
                onChange={(value) => setStatus(value)}
                options={[
                  { value: '', label: 'All Status' },
                  { value: 'pending', label: 'Pending' },
                  { value: 'reviewed', label: 'Reviewed' },
                  { value: 'resolved', label: 'Resolved' },
                ]}
                className="lg:max-w-xs"
              />
            </div>
          </div>
        )}

        {/* Sessions Tab */}
        {activeTab === 'sessions' && (
          <>
            {sessionsLoading && <div className="p-4 sm:p-6"><ShimmerLoader lines={5} /></div>}
            {sessionsError && <div className="p-4 sm:p-6 text-error">Failed to load fraud flags</div>}

            {sessionsData && (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border">
                  <thead className="bg-bg-muted">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">ID</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">User</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Type</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Severity</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Created</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {sessionsData.items.map((flag) => (
                      <tr key={flag.id} className="hover:bg-bg-hover">
                        <td className="px-4 py-3 text-sm text-text-main">{flag.id}</td>
                        <td className="px-4 py-3 text-sm text-text-main">{flag.user_id ?? '-'}</td>
                        <td className="px-4 py-3 text-sm text-text-main">{flag.flag_type}</td>
                        <td className="px-4 py-3 text-sm text-text-main"><Badge variant={flag.severity === 'high' ? 'error' : flag.severity === 'medium' ? 'warning' : 'neutral'}>{flag.severity}</Badge></td>
                        <td className="px-4 py-3 text-sm text-text-main"><Badge variant={flag.status === 'pending' ? 'warning' : flag.status === 'resolved' ? 'success' : 'info'}>{flag.status}</Badge></td>
                        <td className="px-4 py-3 text-sm text-text-main">{new Date(flag.created_at).toLocaleString()}</td>
                        <td className="px-4 py-3 text-sm">
                          {flag.status === 'pending' && (
                            <div className="flex gap-2">
                              <Tooltip content="Mark as resolved - legitimate activity" position="top">
                                <Button
                                  variant="primary"
                                  size="sm"
                                  onClick={() => handleResolveClick(flag.id)}
                                  disabled={resolveMutation.isPending}
                                >
                                  <CheckCircle size={14} className="mr-1" />
                                  Resolve
                                </Button>
                              </Tooltip>
                              <Tooltip content="Mark as false positive" position="top">
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleIgnoreClick(flag.id)}
                                  disabled={ignoreMutation.isPending}
                                >
                                  <XCircle size={14} className="mr-1" />
                                  Ignore
                                </Button>
                              </Tooltip>
                            </div>
                          )}
                          {flag.status !== 'pending' && (
                            <span className="text-text-muted text-xs">{flag.status}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {sessionsData.items.length === 0 && (
                  <p className="p-4 text-center text-text-muted">No suspicious sessions found</p>
                )}
              </div>
            )}
          </>
        )}

        {/* Duplicates Tab */}
        {activeTab === 'duplicates' && (
          <>
            {duplicatesLoading && <div className="p-4 sm:p-6"><ShimmerLoader lines={5} /></div>}
            {duplicatesError && <div className="p-4 sm:p-6 text-error">Failed to load duplicate accounts</div>}

            {duplicatesData && (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border">
                  <thead className="bg-bg-muted">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">ID</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">User</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Details</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Severity</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Created</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {duplicatesData.items.map((flag) => (
                      <tr key={flag.id} className="hover:bg-bg-hover">
                        <td className="px-4 py-3 text-sm text-text-main">{flag.id}</td>
                        <td className="px-4 py-3 text-sm text-text-main">{flag.user_id ?? '-'}</td>
                        <td className="px-4 py-3 text-sm text-text-main max-w-xs truncate">{flag.details}</td>
                        <td className="px-4 py-3 text-sm text-text-main"><Badge variant={flag.severity === 'high' ? 'error' : flag.severity === 'medium' ? 'warning' : 'neutral'}>{flag.severity}</Badge></td>
                        <td className="px-4 py-3 text-sm text-text-main"><Badge variant={flag.status === 'pending' ? 'warning' : flag.status === 'resolved' ? 'success' : 'info'}>{flag.status}</Badge></td>
                        <td className="px-4 py-3 text-sm text-text-main">{new Date(flag.created_at).toLocaleString()}</td>
                        <td className="px-4 py-3 text-sm">
                          {flag.status === 'pending' && (
                            <div className="flex gap-2">
                              <Tooltip content="Mark as resolved - legitimate activity" position="top">
                                <Button
                                  variant="primary"
                                  size="sm"
                                  onClick={() => handleResolveClick(flag.id)}
                                  disabled={resolveMutation.isPending}
                                >
                                  <CheckCircle size={14} className="mr-1" />
                                  Resolve
                                </Button>
                              </Tooltip>
                              <Tooltip content="Mark as false positive" position="top">
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleIgnoreClick(flag.id)}
                                  disabled={ignoreMutation.isPending}
                                >
                                  <XCircle size={14} className="mr-1" />
                                  Ignore
                                </Button>
                              </Tooltip>
                            </div>
                          )}
                          {flag.status !== 'pending' && (
                            <span className="text-text-muted text-xs">{flag.status}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {duplicatesData.items.length === 0 && (
                  <p className="p-4 text-center text-text-muted">No duplicate accounts found</p>
                )}
              </div>
            )}
          </>
        )}

        {/* Referrals Tab */}
        {activeTab === 'referrals' && (
          <>
            {referralsLoading && <div className="p-4 sm:p-6"><ShimmerLoader lines={5} /></div>}
            {referralsError && <div className="p-4 sm:p-6 text-error">Failed to load referral abuse</div>}

            {referralsData && (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border">
                  <thead className="bg-bg-muted">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">ID</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">User</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Details</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Severity</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Created</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {referralsData.items.map((flag) => (
                      <tr key={flag.id} className="hover:bg-bg-hover">
                        <td className="px-4 py-3 text-sm text-text-main">{flag.id}</td>
                        <td className="px-4 py-3 text-sm text-text-main">{flag.user_id ?? '-'}</td>
                        <td className="px-4 py-3 text-sm text-text-main max-w-xs truncate">{flag.details}</td>
                        <td className="px-4 py-3 text-sm text-text-main"><Badge variant={flag.severity === 'high' ? 'error' : flag.severity === 'medium' ? 'warning' : 'neutral'}>{flag.severity}</Badge></td>
                        <td className="px-4 py-3 text-sm text-text-main"><Badge variant={flag.status === 'pending' ? 'warning' : flag.status === 'resolved' ? 'success' : 'info'}>{flag.status}</Badge></td>
                        <td className="px-4 py-3 text-sm text-text-main">{new Date(flag.created_at).toLocaleString()}</td>
                        <td className="px-4 py-3 text-sm">
                          {flag.status === 'pending' && (
                            <div className="flex gap-2">
                              <Tooltip content="Mark as resolved - legitimate activity" position="top">
                                <Button
                                  variant="primary"
                                  size="sm"
                                  onClick={() => handleResolveClick(flag.id)}
                                  disabled={resolveMutation.isPending}
                                >
                                  <CheckCircle size={14} className="mr-1" />
                                  Resolve
                                </Button>
                              </Tooltip>
                              <Tooltip content="Mark as false positive" position="top">
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleIgnoreClick(flag.id)}
                                  disabled={ignoreMutation.isPending}
                                >
                                  <XCircle size={14} className="mr-1" />
                                  Ignore
                                </Button>
                              </Tooltip>
                            </div>
                          )}
                          {flag.status !== 'pending' && (
                            <span className="text-text-muted text-xs">{flag.status}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {referralsData.items.length === 0 && (
                  <p className="p-4 text-center text-text-muted">No referral abuse found</p>
                )}
              </div>
            )}
          </>
        )}
      </Card>
      </Container>

      {/* Resolve Modal */}
      <ConfirmModal
        isOpen={resolveModalOpen}
        onClose={() => {
          setResolveModalOpen(false);
          setResolveNotes('');
        }}
        onConfirm={handleResolveConfirm}
        title="Resolve Fraud Flag"
        message="Mark this fraud flag as resolved (legitimate activity confirmed)."
        confirmText="Resolve"
        variant="primary"
        isLoading={resolveMutation.isPending}
      >
        <div className="mt-4">
          <label className="block text-sm font-medium text-text-main mb-2">
            Resolution Notes (Optional)
          </label>
          <textarea
            value={resolveNotes}
            onChange={(e) => setResolveNotes(e.target.value)}
            className="w-full rounded-md border border-border bg-bg-main px-3 py-2 text-text-main placeholder-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            rows={3}
            placeholder="Add any notes about why this flag was resolved..."
          />
        </div>
      </ConfirmModal>

      {/* Ignore Modal */}
      <ConfirmModal
        isOpen={ignoreModalOpen}
        onClose={() => {
          setIgnoreModalOpen(false);
          setIgnoreReason('');
        }}
        onConfirm={handleIgnoreConfirm}
        title="Ignore Fraud Flag"
        message="Mark this fraud flag as a false positive."
        confirmText="Ignore"
        variant="secondary"
        isLoading={ignoreMutation.isPending}
      >
        <div className="mt-4">
          <label className="block text-sm font-medium text-text-main mb-2">
            Reason (Required) <span className="text-error">*</span>
          </label>
          <textarea
            value={ignoreReason}
            onChange={(e) => setIgnoreReason(e.target.value)}
            className="w-full rounded-md border border-border bg-bg-main px-3 py-2 text-text-main placeholder-text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            rows={3}
            placeholder="Explain why this is a false positive..."
            required
          />
        </div>
      </ConfirmModal>
    </>
  );
}
