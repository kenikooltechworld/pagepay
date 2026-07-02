import { useQuery } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';
import type { FraudFlagListResponse } from '@/lib/types';
import { useState } from 'react';
import { Card, Badge, ShimmerLoader, Container } from '@/shared/components';
import { TopHeader } from '@/shared/components/TopHeader';
import { useLayoutContext } from '@/shared/components/Layout';
import { Select } from '@/shared/components/Select';
import { AlertCircle, Copy, Users } from 'lucide-react';

export function FraudPage() {
  const { onMenuClick } = useLayoutContext();
  const [activeTab, setActiveTab] = useState<'sessions' | 'duplicates' | 'referrals'>('sessions');
  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');

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

  return (
    <>
      <TopHeader title="Fraud Detection" subtitle="Review flagged sessions and abuse patterns" onMenuClick={onMenuClick} />
      <Container size="full">
        <Card>
        {/* Tabs */}
        <div className="flex gap-2 border-b border-border px-4 pt-4">
          <button
            onClick={() => setActiveTab('sessions')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
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
            className={`px-4 py-2 text-sm font-medium transition-colors ${
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
            className={`px-4 py-2 text-sm font-medium transition-colors ${
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
                onChange={(e) => setSeverity(e.target.value)}
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
                onChange={(e) => setStatus(e.target.value)}
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
                      </tr>
                    ))}
                  </tbody>
                </table>
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
    </>
  );
}
