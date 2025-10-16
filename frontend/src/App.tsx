/**
 * Main App component with routing.
 */

import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import { Dashboard } from './components/Dashboard/Dashboard';
import { SceneEditor } from './components/Scenes/SceneEditor';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
}

function LoginPage() {
  const { login, error, isLoading } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const username = formData.get('username') as string;
    const password = formData.get('password') as string;

    try {
      await login(username, password);
      window.location.href = '/';
    } catch (err) {
      // Error is handled in store
    }
  };

  return (
    <div className="login-page">
      <h1>Login</h1>
      <form onSubmit={handleSubmit}>
        <input name="username" placeholder="Username" required />
        <input name="password" type="password" placeholder="Password" required />
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Loading...' : 'Login'}
        </button>
        {error && <div className="error">{error}</div>}
      </form>
    </div>
  );
}

export function App() {
  const loadUser = useAuthStore((state) => state.loadUser);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Dashboard />
            </PrivateRoute>
          }
        />
        <Route
          path="/scenes/:sceneId"
          element={
            <PrivateRoute>
              <SceneEditor />
            </PrivateRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
