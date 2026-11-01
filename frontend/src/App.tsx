import { useEffect, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { TopBar } from "@/components/shell/TopBar";
import { Sidebar } from "@/components/shell/Sidebar";
import ComposePage from "@/pages/ComposePage";
import ReviewQueuePage from "@/pages/ReviewQueuePage";
import ProductsFactsPage from "@/pages/ProductsFactsPage";
import AlertsPage from "@/pages/AlertsPage";
import AnalyticsPage from "@/pages/AnalyticsPage";
import ContentPage from "@/pages/ContentPage";
import BrandGuidelinesPage from "@/pages/BrandGuidelinesPage";
import RoutePlaceholder from "@/pages/RoutePlaceholder";
import BrandRulesPage from "@/pages/BrandRulesPage";
import IntakePage from "@/pages/IntakePage";
import NotificationsPage from "@/pages/NotificationsPage";
import SettingsPage from "@/pages/SettingsPage";
import LoginPage from "@/pages/LoginPage";

import { api, getToken, setToken } from "@/api/client";
import { getAlerts } from "@/api/alerts";
import type { DemoUser, UserRole } from "@/types";

function AuthenticatedApp() {
  const [currentUser, setCurrentUser] = useState<DemoUser | null>(null);
  const role: UserRole = currentUser?.role ?? "creator";
  const [authReady, setAuthReady] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [alertCount, setAlertCount] = useState<number>(0);

  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!currentUser) return;
    getAlerts()
      .then((items) => {
        setAlertCount(items.filter((a) => a.status === "open").length);
      })
      .catch(() => setAlertCount(0));
  }, [currentUser, location.pathname]);

  useEffect(() => {
    let cancelled = false;

    async function validateSession() {
      if (!getToken()) {
        if (!cancelled) setAuthReady(true);
        return;
      }

      try {
        const user = await api.getMe();

        if (!cancelled) {
          setCurrentUser(user);
          setAuthReady(true);
        }
      } catch {
        setToken(null);

        if (!cancelled) setAuthReady(true);
      }
    }

    void validateSession();

    return () => {
      cancelled = true;
    };
  }, []);

  if (!authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#F6F8FC]">
        Checking session...
      </div>
    );
  }

  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }

  if (!currentUser) return null;
  const user = currentUser;

  return (
    <div className="min-h-screen bg-[#F6F8FC] text-[#1F2937]">
      <TopBar
        user={user}
        onUserChange={setCurrentUser}
        onMenuClick={() => setMobileNavOpen(true)}
        onNavigate={navigate}
      />

      <div className="mx-auto flex h-[calc(100vh-56px)] max-w-[1800px]">
        <Sidebar
          role={role}
          mobileOpen={mobileNavOpen}
          onClose={() => setMobileNavOpen(false)}
          alertCount={alertCount}
        />

        <main
          id="main-content"
          className="min-w-0 flex-1 overflow-hidden px-3 py-2"
        >
          <div className="mx-auto h-full max-w-[1600px]">
            <Routes>
              <Route path="/content" element={<ContentPage />} />
              <Route path="/content/compose" element={<ComposePage />} />
              <Route path="/review-queue" element={<ReviewQueuePage />} />
              <Route path="/guidelines" element={<BrandGuidelinesPage role={role} currentUserId={user.id} />} />
              <Route path="/facts" element={<ProductsFactsPage />} />
              <Route
                path="/products-facts"
                element={<Navigate to="/facts" replace />}
              />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/brand-rules" element={<BrandRulesPage role={role} currentUserId={user.id} />} />
              <Route path="/intake" element={<IntakePage role={role} />} />
              <Route path="/notifications" element={<NotificationsPage role={role} />} />
              <Route path="/settings" element={<SettingsPage user={user} />} />
              <Route path="*" element={<RoutePlaceholder />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const location = useLocation();

  if (location.pathname === "/login") {
    return <LoginPage />;
  }

  if (location.pathname === "/") {
    return <Navigate to="/content" replace />;
  }

  return <AuthenticatedApp />;
}
