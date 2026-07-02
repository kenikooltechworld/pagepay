import { useQuery } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';
import type { DashboardStats, DailyActiveUsers } from '@/lib/types';
import { StatCard, Card } from '@/shared/components/Card';
import { TopHeader } from '@/shared/components/TopHeader';
import { BarChart } from '@/shared/components/BarChart';
import { ShimmerLoader } from '@/shared/components/ShimmerLoader';
import { Container } from '@/shared/components/Container';
import { useLayoutContext } from '@/shared/components/Layout';

function formatNgn(kobo: number) {
  return `₦${(kobo / 100).toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function DashboardPage() {
  const { onMenuClick } = useLayoutContext();
  const { data: stats, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['admin', 'dashboard', 'stats'],
    queryFn: async () => {
      const { data } = await adminApi.get<DashboardStats>('/admin/dashboard/stats');
      return data;
    },
    staleTime: 60_000,
  });

  const { data: dau = [], isLoading: dauLoading } = useQuery({
    queryKey: ['admin', 'analytics', 'dau'],
    queryFn: async () => {
      const { data } = await adminApi.get<DailyActiveUsers[]>('/admin/analytics/dau', {
        params: { days: 7 },
      });
      return data;
    },
    staleTime: 60_000,
  });

  return (
    <>
      <TopHeader title="Dashboard" subtitle="Platform overview and key metrics" onMenuClick={onMenuClick} />
      <Container size="lg">
        <div className="space-y-6">
          {statsLoading && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              <ShimmerLoader lines={6} />
            </div>
          )}
          {statsError && <Card className="p-4 text-error">Failed to load dashboard</Card>}
          {stats && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              <StatCard label="Total Users" value={stats.total_users.toLocaleString()} />
              <StatCard label="Active Today" value={stats.active_users_today.toLocaleString()} />
              <StatCard label="Revenue" value={formatNgn(stats.total_revenue_ngn)} />
              <StatCard label="Pending Payouts" value={stats.pending_payouts.toLocaleString()} />
              <StatCard label="Pending Notes" value={stats.pending_notes.toLocaleString()} />
              <StatCard label="High Fraud Flags" value={stats.high_severity_fraud_flags.toLocaleString()} />
            </div>
          )}

          <Card>
            <div className="border-b border-border px-4 py-4 sm:px-6">
              <h3 className="text-sm font-semibold text-text-main">Daily Active Users</h3>
              <p className="mt-0.5 text-sm text-text-muted">Last 7 days</p>
            </div>
            <div className="p-4 sm:p-6">
              {dauLoading && <ShimmerLoader lines={4} />}
              {!dauLoading && dau.length > 0 && (
                <BarChart data={dau} height={300} />
              )}
            </div>
          </Card>
        </div>
      </Container>
    </>
  );
}
