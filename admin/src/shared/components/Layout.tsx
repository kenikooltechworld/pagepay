import { useState } from 'react';
import { Outlet, useOutletContext, Navigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Navbar } from './Navbar';
import { useAuthStore } from '@/store/auth';
import { adminApi } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import type { AdminUserOut } from '@/lib/types';

/**
 * Shape of the context passed to routed children via <Outlet />.
 * Pages call `useLayoutContext()` to get a typed reference.
 */
export interface LayoutContext {
  onMenuClick: () => void;
}

/**
 * Authenticated app shell. Owns:
 *   - the auth gate (redirects to /login when no auth)
 *   - the mobile sidebar open/close state
 *   - the desktop sidebar (fixed, hidden on mobile)
 *   - the mobile overlay drawer (which reuses the same <Sidebar /> panel)
 *   - the top <Navbar /> above the routed content
 *   - the <Outlet context={...} /> for pages to receive onMenuClick
 */
export function Layout() {
  const { isAuthenticated, setAuth, clearAuth } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Check auth status by calling /admin/auth/me
  // If httpOnly cookie is valid, backend returns admin info
  const { data: admin, isLoading, error } = useQuery({
    queryKey: ['admin', 'me'],
    queryFn: async () => {
      const { data } = await adminApi.get<AdminUserOut>('/admin/auth/me');
      return data;
    },
    retry: false,
    staleTime: 60_000,
    onSuccess: (data) => {
      if (!isAuthenticated) {
        setAuth(data.role, []); // Permissions need to be fetched separately or included in /me response
      }
    },
    onError: () => {
      if (isAuthenticated) {
        clearAuth();
      }
    },
  });

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg-body">
        <div className="text-text-muted">Loading...</div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!admin) {
    return <Navigate to="/login" replace />;
  }

  const ctx: LayoutContext = { onMenuClick: () => setSidebarOpen(true) };

  return (
    <div className="flex min-h-screen bg-bg-body">
      {/* Desktop sidebar — fixed, visible at md+ */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden border-r border-border md:block">
        <Sidebar />
      </aside>

      {/* Mobile overlay drawer — modal, md:hidden */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-50 flex md:hidden"
          role="dialog"
          aria-modal="true"
        >
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative h-full">
            <Sidebar
              onNavigate={() => setSidebarOpen(false)}
              onClose={() => setSidebarOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Main column — offset for the desktop sidebar */}
      <main className="flex min-h-screen flex-1 flex-col overflow-x-hidden md:ml-64 pt-14">
        <Navbar onMenuClick={() => setSidebarOpen(true)} />
        <div className="flex-1">
          <Outlet context={ctx} />
        </div>
      </main>
    </div>
  );
}

/**
 * Typed accessor for the Outlet context. Pages should use this instead of
 * calling useOutletContext directly so the context shape stays in sync.
 */
export function useLayoutContext(): LayoutContext {
  return useOutletContext<LayoutContext>();
}

