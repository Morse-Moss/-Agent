import { ConfigProvider } from "antd";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { isAuthenticated } from "./lib/auth";
import { BrandPage } from "./pages/BrandPage";
import { CreatePage } from "./pages/CreatePage";
import { LoginPage } from "./pages/LoginPage";
import { ProjectDetailPage } from "./pages/ProjectDetailPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { SettingsPage } from "./pages/SettingsPage";

function RequireAuth({ children }: { children: JSX.Element }): JSX.Element {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export function App(): JSX.Element {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#0f3d3e",
          colorInfo: "#0f3d3e",
          borderRadius: 18,
          fontFamily: '"Segoe UI", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/" element={<Navigate to="/create" replace />} />
            <Route path="/create" element={<CreatePage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
            <Route path="/brand" element={<BrandPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
