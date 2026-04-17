import { type ReactElement } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { usePortfolio } from './context/PortfolioContext';
import ToolpadShell from './layouts/ToolpadShell';
import { ROUTES } from './config/routes.config';

import SettingsShell from './layouts/SettingsShell';
import ProfileSettings from './pages/settings/ProfileSettings';
import SecuritySettings from './pages/settings/SecuritySettings';
import ModuleSettings from './pages/settings/ModuleSettings';
import ProjectModuleSettings from './pages/settings/ProjectModuleSettings';
import PortfolioModuleSettings from './pages/settings/PortfolioModuleSettings';

// Eagerly loaded pages (critical path)
import Login from './pages/Login';
import SelectPortfolio from './pages/SelectPortfolio';
import Landing from './pages/Landing';
import NotFound from './pages/NotFound';

/**
 * Private route wrapper.
 * Redirects unauthenticated users to login.
 * Redirects authenticated users without a portfolio to selection.
 */
function PrivateRoute({ children }: { children: ReactElement }) {
  const { isAuthenticated } = useAuth();
  const { hasActivePortfolio } = usePortfolio();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} state={{ from: location }} replace />;
  }

  if (!hasActivePortfolio) {
    // If we are already on the selection page, don't redirect (avoids loop if we use this wrapper there, 
    // but we won't wrap SelectPortfolio in PrivateRoute with check for project)
    return <Navigate to={ROUTES.SELECT_PORTFOLIO} replace />;
  }

  return children;
}

/**
 * AppRoutes component.
 * Registers all application routes in a single location.
 */
export default function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path={ROUTES.LOGIN} element={<Login />} />

      {/* Auth-only routes (no portfolio required) */}
      <Route path={ROUTES.SELECT_PORTFOLIO} element={<SelectPortfolio />} />

      {/* Protected routes (require auth + portfolio) */}
      <Route
        path={ROUTES.HOME}
        element={
          <PrivateRoute>
            <ToolpadShell>
              <Landing />
            </ToolpadShell>
          </PrivateRoute>
        }
      />

      {/* Settings Routes - Dedicated Shell */}
      <Route
        path="/settings/*"
        element={
          <PrivateRoute>
            <SettingsShell>
              <Routes>
                <Route path="/" element={<Navigate to="profile" replace />} />
                <Route path="profile" element={<ProfileSettings />} />
                <Route path="security" element={<SecuritySettings />} />
                <Route path="modules" element={<ModuleSettings />} />
                <Route path="modules/projects" element={<ProjectModuleSettings />} />
                <Route path="modules/portfolios" element={<PortfolioModuleSettings />} />
              </Routes>
            </SettingsShell>
          </PrivateRoute>
        }
      />

      {/* 404 catch-all route */}
      <Route path={ROUTES.NOT_FOUND} element={<NotFound />} />
    </Routes>
  );
}
