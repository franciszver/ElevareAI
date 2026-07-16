import { createContext, useContext, useState, useEffect, useRef } from 'react';
import { login as apiLogin, register as apiRegister, getCurrentUser } from '../utils/auth';
import { TOKEN_KEY } from '../services/apiClient';

const AuthContext = createContext();

export { TOKEN_KEY };

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  // Set when login/signup completes while the mount-time token validation may
  // still be in flight, so its stale result doesn't clobber fresh auth state.
  const authChangedRef = useRef(false);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);

    if (!token) {
      setLoading(false);
      return;
    }

    // Validate the stored token against the backend
    getCurrentUser()
      .then((dbUser) => {
        if (authChangedRef.current) return;
        setUser({ id: dbUser.id, email: dbUser.email, role: dbUser.role });
        setIsAuthenticated(true);
      })
      .catch(() => {
        if (authChangedRef.current) return;
        localStorage.removeItem(TOKEN_KEY);
        setIsAuthenticated(false);
        setUser(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const login = async (email, password) => {
    try {
      const { token, user: loggedInUser } = await apiLogin(email, password);

      authChangedRef.current = true;
      localStorage.setItem(TOKEN_KEY, token);
      setIsAuthenticated(true);
      setUser(loggedInUser);

      return { success: true };
    } catch (error) {
      const message =
        error.response?.data?.detail || error.message || 'Login failed';
      return { success: false, error: message };
    }
  };

  const signup = async (email, password, name, role) => {
    try {
      await apiRegister(email, password, name, role);
      // Auto-login after successful registration
      return await login(email, password);
    } catch (error) {
      const message =
        error.response?.data?.detail || error.message || 'Signup failed';
      return { success: false, error: message };
    }
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setIsAuthenticated(false);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
