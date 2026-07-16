import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Dashboard from './pages/Dashboard';
import Practice from './pages/Practice';
import QA from './pages/QA';
import Progress from './pages/Progress';
import Goals from './pages/Goals';
import Settings from './pages/Settings';
import Messaging from './pages/Messaging';
import Login from './pages/Login';
import Signup from './pages/Signup';
import ForgotPassword from './pages/ForgotPassword';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ToastProvider, useToast } from './contexts/ToastContext';
import Navbar from './components/Navbar';
import ToastContainer from './components/ToastContainer';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();

  // Check localStorage as fallback (handles timing issues)
  const hasToken = localStorage.getItem('elevare_token');

  console.log('[PROTECTED] Route check:', {
    isAuthenticated,
    loading,
    hasToken: !!hasToken,
    path: window.location.pathname
  });
  
  if (loading) {
    console.log('[PROTECTED] Still loading, showing loading screen');
    return <div>Loading...</div>;
  }
  
  if (isAuthenticated || hasToken) {
    console.log('[PROTECTED] Access granted, rendering children');
    return children;
  }
  
  console.log('[PROTECTED] Access denied, redirecting to login');
  return <Navigate to="/login" replace />;
}

function AppContent() {
  const { toasts, removeToast } = useToast();
  
  return (
    <Router>
      <div className="app">
        <Navbar />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/practice"
            element={
              <ProtectedRoute>
                <Practice />
              </ProtectedRoute>
            }
          />
          <Route
            path="/qa"
            element={
              <ProtectedRoute>
                <QA />
              </ProtectedRoute>
            }
          />
              <Route
                path="/progress"
                element={
                  <ProtectedRoute>
                    <Progress />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/goals"
                element={
                  <ProtectedRoute>
                    <Goals />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <Settings />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/messaging"
                element={
                  <ProtectedRoute>
                    <Messaging />
                  </ProtectedRoute>
                }
              />
              <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
        <ToastContainer toasts={toasts} onRemove={removeToast} />
      </div>
    </Router>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>
          <AppContent />
        </ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;

