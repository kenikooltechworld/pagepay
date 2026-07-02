import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';
import type { UserDetail, UserSessionsResponse, UserTransactionsResponse } from '@/lib/types';
import { Modal, Badge, Button, ShimmerLoader } from '@/shared/components';
import { useAuthStore } from '@/store/auth';
import { DollarSign, Activity, Receipt, Calendar, User as UserIcon } from 'lucide-react';
import React from 'react';

interface UserDetailModalProps {
  userId: number | null;
  onClose: () => void;
}

export function UserDetailModal({ userId, onClose }: UserDetailModalProps) {
  const queryClient = useQueryClient();
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const [activeTab, setActiveTab] = React.useState<'details' | 'sessions' | 'transactions'>('details');

  const { data: user, isLoading: userLoading } = useQuery({
    queryKey: ['admin', 'users', userId],
    queryFn: async () => {
      if (!userId) return null;
      const { data } = await adminApi.get<UserDetail>(`/admin/users/${userId}`);
      return data;
    },
    enabled: !!userId,
    staleTime: 30_000,
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery({
    queryKey: ['admin', 'users', userId, 'sessions'],
    queryFn: async () => {
      if (!userId) return null;
      const { data } = await adminApi.get<UserSessionsResponse>(`/admin/users/${userId}/sessions`, {
        params: { page: 1, limit: 20 },
      });
      return data;
    },
    enabled: !!userId && activeTab === 'sessions',
    staleTime: 30_000,
  });

  const { data: transactions, isLoading: transactionsLoading } = useQuery({
    queryKey: ['admin', 'users', userId, 'transactions'],
    queryFn: async () => {
      if (!userId) return null;
      const { data } = await adminApi.get<UserTransactionsResponse>(`/admin/users/${userId}/transactions`, {
        params: { page: 1, limit: 20 },
      });
      return data;
    },
    enabled: !!userId && activeTab === 'transactions',
    staleTime: 30_000,
  });

  const adjustBalanceMutation = useMutation({
    mutationFn: async ({ userId, amount, reason }: { userId: number; amount: number; reason: string }) => {
      await adminApi.post(`/admin/users/${userId}/adjust-balance`, null, {
        params: { amount, reason },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });

  const handleAdjustBalance = () => {
    if (!userId) return;
    const amountStr = prompt('Enter amount to adjust (positive to add, negative to subtract):');
    if (!amountStr) return;
    const amount = parseInt(amountStr, 10);
    if (isNaN(amount)) {
      alert('Invalid amount');
      return;
    }
    const reason = prompt('Reason for adjustment:');
    if (!reason) return;
    adjustBalanceMutation.mutate({ userId, amount, reason });
  };

  if (!userId) return null;

  return (
    <Modal
      isOpen={!!userId}
      onClose={onClose}
      title={user ? `User: ${user.email}` : 'User Details'}
    >
      <div className="space-y-4">
        {/* Tabs */}
        <div className="flex gap-2 border-b border-border">
          <button
            onClick={() => setActiveTab('details')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'details'
                ? 'border-b-2 border-primary text-primary'
                : 'text-text-muted hover:text-text-main'
            }`}
          >
            <UserIcon size={16} className="mr-1.5 inline" />
            Details
          </button>
          <button
            onClick={() => setActiveTab('sessions')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'sessions'
                ? 'border-b-2 border-primary text-primary'
                : 'text-text-muted hover:text-text-main'
            }`}
          >
            <Activity size={16} className="mr-1.5 inline" />
            Sessions
          </button>
          <button
            onClick={() => setActiveTab('transactions')}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === 'transactions'
                ? 'border-b-2 border-primary text-primary'
                : 'text-text-muted hover:text-text-main'
            }`}
          >
            <Receipt size={16} className="mr-1.5 inline" />
            Transactions
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'details' && (
          <>
            {userLoading && <ShimmerLoader lines={6} />}
            {user && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-text-muted">ID:</span>
                    <p className="font-medium text-text-main">{user.id}</p>
                  </div>
                  <div>
                    <span className="text-text-muted">Email:</span>
                    <p className="font-medium text-text-main">{user.email}</p>
                  </div>
                  <div>
                    <span className="text-text-muted">Phone:</span>
                    <p className="font-medium text-text-main">{user.phone || '-'}</p>
                  </div>
                  <div>
                    <span className="text-text-muted">Tier:</span>
                    <p className="font-medium text-text-main">
                      <Badge variant="neutral">{user.tier}</Badge>
                    </p>
                  </div>
                  <div>
                    <span className="text-text-muted">Status:</span>
                    <p className="font-medium text-text-main">
                      <Badge variant={user.status === 'active' ? 'success' : 'error'}>{user.status}</Badge>
                    </p>
                  </div>
                  <div>
                    <span className="text-text-muted">Points Balance:</span>
                    <p className="font-medium text-text-main">{user.points_balance.toLocaleString()}</p>
                  </div>
                  <div>
                    <span className="text-text-muted">Referral Code:</span>
                    <p className="font-medium text-text-main">{user.referral_code || '-'}</p>
                  </div>
                  <div>
                    <span className="text-text-muted">Referred By:</span>
                    <p className="font-medium text-text-main">{user.referred_by || '-'}</p>
                  </div>
                  <div>
                    <span className="text-text-muted">Created:</span>
                    <p className="font-medium text-text-main">
                      <Calendar size={14} className="mr-1 inline" />
                      {new Date(user.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div>
                    <span className="text-text-muted">Last Active:</span>
                    <p className="font-medium text-text-main">
                      {user.last_active_at ? new Date(user.last_active_at).toLocaleDateString() : '-'}
                    </p>
                  </div>
                  {user.subscription_expires_at && (
                    <div className="col-span-2">
                      <span className="text-text-muted">Subscription Expires:</span>
                      <p className="font-medium text-text-main">
                        {new Date(user.subscription_expires_at).toLocaleDateString()}
                      </p>
                    </div>
                  )}
                </div>

                {hasPermission('users.adjust_balance') && (
                  <div className="mt-4 flex justify-end">
                    <Button
                      onClick={handleAdjustBalance}
                      variant="secondary"
                      disabled={adjustBalanceMutation.isPending}
                    >
                      <DollarSign size={16} />
                      {adjustBalanceMutation.isPending ? 'Adjusting...' : 'Adjust Balance'}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {activeTab === 'sessions' && (
          <>
            {sessionsLoading && <ShimmerLoader lines={5} />}
            {sessions && sessions.items.length > 0 && (
              <div className="max-h-96 overflow-y-auto">
                <table className="min-w-full divide-y divide-border text-sm">
                  <thead className="bg-bg-muted sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-text-muted">Content ID</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-text-muted">Duration</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-text-muted">Points</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-text-muted">Verified</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-text-muted">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {sessions.items.map((session) => (
                      <tr key={session.id} className="hover:bg-bg-hover">
                        <td className="px-3 py-2">{session.content_id}</td>
                        <td className="px-3 py-2">{Math.round(session.duration_seconds / 60)}m</td>
                        <td className="px-3 py-2">{session.points_earned}</td>
                        <td className="px-3 py-2">
                          <Badge variant={session.verified ? 'success' : 'warning'}>
                            {session.verified ? 'Yes' : 'No'}
                          </Badge>
                        </td>
                        <td className="px-3 py-2">{new Date(session.start_time).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-xs text-text-muted">
                  Showing {sessions.items.length} of {sessions.total} sessions
                </p>
              </div>
            )}
            {sessions && sessions.items.length === 0 && (
              <p className="text-center text-text-muted">No sessions found</p>
            )}
          </>
        )}

        {activeTab === 'transactions' && (
          <>
            {transactionsLoading && <ShimmerLoader lines={5} />}
            {transactions && transactions.items.length > 0 && (
              <div className="max-h-96 overflow-y-auto">
                <table className="min-w-full divide-y divide-border text-sm">
                  <thead className="bg-bg-muted sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-text-muted">Type</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-text-muted">ID</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-text-muted">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {transactions.items.map((txn, idx) => (
                      <tr key={`${txn.type}-${txn.id}-${idx}`} className="hover:bg-bg-hover">
                        <td className="px-3 py-2">
                          <Badge variant="neutral">{txn.type}</Badge>
                        </td>
                        <td className="px-3 py-2">{txn.id}</td>
                        <td className="px-3 py-2">{new Date(txn.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-xs text-text-muted">
                  Showing {transactions.items.length} of {transactions.total} transactions
                </p>
              </div>
            )}
            {transactions && transactions.items.length === 0 && (
              <p className="text-center text-text-muted">No transactions found</p>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
