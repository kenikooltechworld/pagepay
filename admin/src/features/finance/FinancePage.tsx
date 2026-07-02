import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';
import type { RevenueSummary, PayoutListResponse } from '@/lib/types';
import { useState } from 'react';
import { Card, StatCard, Badge, Button, Pagination, ShimmerLoader, Container } from '@/shared/components';
import { TopHeader } from '@/shared/components/TopHeader';
import { useLayoutContext } from '@/shared/components/Layout';
import { useAuthStore } from '@/store/auth';
import { CheckCircle, XCircle } from 'lucide-react';

export function FinancePage() {
  const { onMenuClick } = useLayoutContext();
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const [tab, setTab] = useState<'revenue' | 'payouts'>('revenue');
  const [payoutPage, setPayoutPage] = useState(1);

  const queryClient = useQueryClient();

  const { data: revenue, isLoading: revenueLoading } = useQuery({
    queryKey: ['admin', 'finance', 'revenue'],
    queryFn: async () => {
      const { data } = await adminApi.get<RevenueSummary>('/admin/revenue/summary');
      return data;
    },
    staleTime: 60_000,
  });

  const { data: payouts, isLoading: payoutsLoading } = useQuery({
    queryKey: ['admin', 'finance', 'payouts', payoutPage],
    queryFn: async () => {
      const { data } = await adminApi.get<PayoutListResponse>('/admin/payouts', {
        params: { page: payoutPage, limit: 50 },
      });
      return data;
    },
    staleTime: 30_000,
  });

  const approveMutation = useMutation({
    mutationFn: async (payoutId: number) => {
      await adminApi.post(`/admin/payouts/${payoutId}/approve`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'finance', 'payouts'] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: async ({ payoutId, reason }: { payoutId: number; reason: string }) => {
      await adminApi.post(`/admin/payouts/${payoutId}/reject`, null, { params: { reason } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'finance', 'payouts'] });
    },
  });

  const handleApprove = (payoutId: number) => {
    if (confirm('Approve this payout?')) {
      approveMutation.mutate(payoutId);
    }
  };

  const handleReject = (payoutId: number) => {
    const reason = prompt('Rejection reason:');
    if (reason && reason.length >= 10) {
      rejectMutation.mutate({ payoutId, reason });
    } else if (reason) {
      alert('Reason must be at least 10 characters');
    }
  };

  return (
    <>
      <TopHeader
        title="Finance"
        subtitle="Revenue and payouts overview"
        onMenuClick={onMenuClick}
        actions={
          <div className="flex rounded-lg border border-border">
            <button
              onClick={() => setTab('revenue')}
              className={`px-4 py-1.5 text-sm font-semibold transition-colors ${tab === 'revenue' ? 'bg-primary text-white' : 'text-text-muted hover:text-text-main'}`}
            >
              Revenue
            </button>
            <button
              onClick={() => setTab('payouts')}
              className={`px-4 py-1.5 text-sm font-semibold transition-colors ${tab === 'payouts' ? 'bg-primary text-white' : 'text-text-muted hover:text-text-main'}`}
            >
              Payouts
            </button>
          </div>
        }
      />
      <Container size="lg">
        {tab === 'revenue' && (
        <div>
          {revenueLoading && <ShimmerLoader lines={4} />}
          {revenue && (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard label="Total Revenue" value={`₦${revenue.total_revenue_ngn.toLocaleString()}`} />
                <StatCard label="Ad Revenue" value={`₦${revenue.ad_revenue_ngn.toLocaleString()}`} />
                <StatCard label="Premium Revenue" value={`₦${revenue.premium_revenue_ngn.toLocaleString()}`} />
                <StatCard label="Gross Profit" value={`₦${revenue.gross_profit_ngn.toLocaleString()}`} />
              </div>
              <p className="mt-4 text-sm text-text-muted">
                Period: {revenue.period_start} → {revenue.period_end}
              </p>
            </>
          )}
        </div>
      )}

      {tab === 'payouts' && (
        <div>
          {payoutsLoading && <ShimmerLoader lines={5} />}
          {payouts && (
            <Card>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-border">
                  <thead className="bg-bg-muted">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">ID</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">User</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Amount</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Fee</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Created</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-text-muted">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {payouts.items.map((p) => (
                      <tr key={p.id} className="hover:bg-bg-hover">
                        <td className="px-4 py-3 text-sm text-text-main">{p.id}</td>
                        <td className="px-4 py-3 text-sm text-text-main">{p.user_id}</td>
                        <td className="px-4 py-3 text-sm text-text-main">₦{(p.amount_kobo / 100).toFixed(2)}</td>
                        <td className="px-4 py-3 text-sm text-text-main">₦{(p.fee_kobo / 100).toFixed(2)}</td>
                        <td className="px-4 py-3 text-sm text-text-main"><Badge variant={p.status === 'success' ? 'success' : p.status === 'failed' ? 'error' : 'warning'}>{p.status}</Badge></td>
                        <td className="px-4 py-3 text-sm text-text-main">{new Date(p.created_at).toLocaleString()}</td>
                        <td className="px-4 py-3 text-sm text-text-main">
                          {hasPermission('finance.approve') && p.status === 'pending' && (
                            <div className="flex gap-2">
                              <Button size="sm" variant="secondary" onClick={() => handleApprove(p.id)}>
                                <CheckCircle size={14} /> Approve
                              </Button>
                              <Button size="sm" variant="danger" onClick={() => handleReject(p.id)}>
                                <XCircle size={14} /> Reject
                              </Button>
                            </div>
                          )}
                          {p.status !== 'pending' && <span className="text-text-muted">-</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="p-4 sm:p-6">
                <Pagination page={payoutPage} totalPages={Math.ceil(payouts.total / 50)} onPageChange={setPayoutPage} />
              </div>
            </Card>
          )}
        </div>
      )}
      </Container>
    </>
  );
}
