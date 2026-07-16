import { useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { useFormValidation } from '../hooks/useFormValidation';
import { validators } from '../utils/validation';
import './Login.css';

function Login() {
  const { login, isAuthenticated } = useAuth();
  const { success, error: showError } = useToast();
  const navigate = useNavigate();

  const loginSchema = {
    email: [validators.required, validators.email],
    password: [validators.required, validators.minLength(6)],
  };

  const {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    validate,
  } = useFormValidation(
    { email: '', password: '' },
    loginSchema
  );

  // Redirect if already authenticated
  useEffect(() => {
    console.log('[LOGIN PAGE] Auth state check:', { isAuthenticated, hasToken: !!localStorage.getItem('elevare_token') });
    if (isAuthenticated || localStorage.getItem('elevare_token')) {
      console.log('[LOGIN PAGE] Already authenticated, redirecting to dashboard');
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  if (isAuthenticated || localStorage.getItem('elevare_token')) {
    return <div>Redirecting...</div>;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validate()) {
      showError('Please fix the errors in the form');
      return;
    }
    
    console.log('[LOGIN] Starting login process', { email: values.email, password: '***' });

    const result = await login(values.email, values.password);
    console.log('[LOGIN] Login result:', result);
    
    if (result.success) {
      console.log('[LOGIN] Login successful, checking auth state...');
      success('Login successful!');
      
      setTimeout(() => {
        const token = localStorage.getItem('elevare_token');
        console.log('[LOGIN] After delay - token exists:', !!token);
        console.log('[LOGIN] Navigating to dashboard...');
        navigate('/dashboard', { replace: true });
      }, 100);
    } else {
      console.error('[LOGIN] Login failed:', result.error);
      showError(result.error || 'Login failed');
    }
  };

  return (
    <div className="login">
      <div className="login-container">
        <img src="/elevare-logo.svg" alt="ElevareAI" style={{ width: '80px', height: '80px', marginBottom: '1rem' }} />
        <h1>ElevareAI</h1>
        <p className="tagline" style={{ marginBottom: '2rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
          Lift your learning, gently.
        </p>
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <input
                    type="email"
                    placeholder="Email"
                    value={values.email}
                    onChange={(e) => handleChange('email', e.target.value)}
                    onBlur={() => handleBlur('email')}
                    required
                    className={touched.email && errors.email ? 'error' : ''}
                  />
                  {touched.email && errors.email && (
                    <span className="error-message">{errors.email}</span>
                  )}
                </div>
                <div className="form-group">
                  <input
                    type="password"
                    placeholder="Password"
                    value={values.password}
                    onChange={(e) => handleChange('password', e.target.value)}
                    onBlur={() => handleBlur('password')}
                    required
                    className={touched.password && errors.password ? 'error' : ''}
                  />
                  {touched.password && errors.password && (
                    <span className="error-message">{errors.password}</span>
                  )}
                </div>
                <div style={{ textAlign: 'right', marginBottom: '1rem' }}>
                  <Link 
                    to="/forgot-password" 
                    style={{ 
                      color: 'var(--primary)', 
                      textDecoration: 'none',
                      fontSize: '0.9rem'
                    }}
                  >
                    Forgot Password?
                  </Link>
                </div>
                <button type="submit">Login</button>
              </form>
        <p style={{ marginTop: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Don't have an account? <Link to="/signup" style={{ color: 'var(--primary)', textDecoration: 'none' }}>Sign up</Link>
        </p>
      </div>
    </div>
  );
}

export default Login;

