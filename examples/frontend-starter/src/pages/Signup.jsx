import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../contexts/ToastContext';
import { useFormValidation } from '../hooks/useFormValidation';
import { validators } from '../utils/validation';
import './Login.css';

const ROLES = ['student', 'tutor', 'parent'];

function Signup() {
  const { signup } = useAuth();
  const { success, error: showError } = useToast();
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [role, setRole] = useState('student');

  const signupSchema = {
    email: [validators.required, validators.email],
    password: [validators.required, validators.passwordPolicy],
    confirmPassword: [
      validators.required,
      (value, allValues) => {
        if (value !== allValues.password) {
          return 'Passwords do not match';
        }
        return null;
      },
    ],
    name: [], // Optional
  };

  const {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    validate,
  } = useFormValidation(
    { email: '', password: '', confirmPassword: '', name: '' },
    signupSchema
  );

  // Helper function to check password requirements
  const checkPasswordRequirements = (password) => {
    return {
      minLength: password.length >= 8,
      hasUppercase: /[A-Z]/.test(password),
      hasLowercase: /[a-z]/.test(password),
      hasNumber: /[0-9]/.test(password),
      hasSymbol: /[^A-Za-z0-9]/.test(password),
    };
  };

  const passwordRequirements = checkPasswordRequirements(values.password);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validate()) {
      showError('Please fix the errors in the form');
      return;
    }

    setIsSubmitting(true);

    try {
      const result = await signup(values.email, values.password, values.name, role);

      if (result.success) {
        success('Account created successfully!');
        navigate('/dashboard', { replace: true });
      } else {
        showError(result.error || 'Signup failed');
      }
    } finally {
      setIsSubmitting(false);
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
              type="text"
              placeholder="Name (optional)"
              value={values.name}
              onChange={(e) => handleChange('name', e.target.value)}
              onBlur={() => handleBlur('name')}
              className={touched.name && errors.name ? 'error' : ''}
            />
            {touched.name && errors.name && (
              <span className="error-message">{errors.name}</span>
            )}
          </div>
          <div className="form-group">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.charAt(0).toUpperCase() + r.slice(1)}
                </option>
              ))}
            </select>
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
            {values.password && (
              <div style={{
                marginTop: '0.5rem',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
                padding: '0.75rem',
                background: 'var(--background-secondary, #f5f5f5)',
                borderRadius: 'var(--border-radius-sm, 4px)',
                border: '1px solid var(--border-color, #ddd)'
              }}>
                <div style={{ marginBottom: '0.5rem', fontWeight: '500' }}>Password must contain:</div>
                <ul style={{ margin: 0, paddingLeft: '1.25rem', listStyle: 'none' }}>
                  <li style={{
                    color: passwordRequirements.minLength ? 'var(--success, #28a745)' : 'var(--text-secondary)',
                    marginBottom: '0.25rem'
                  }}>
                    {passwordRequirements.minLength ? '✓' : '○'} At least 8 characters
                  </li>
                  <li style={{
                    color: passwordRequirements.hasUppercase ? 'var(--success, #28a745)' : 'var(--text-secondary)',
                    marginBottom: '0.25rem'
                  }}>
                    {passwordRequirements.hasUppercase ? '✓' : '○'} One uppercase letter (A-Z)
                  </li>
                  <li style={{
                    color: passwordRequirements.hasLowercase ? 'var(--success, #28a745)' : 'var(--text-secondary)',
                    marginBottom: '0.25rem'
                  }}>
                    {passwordRequirements.hasLowercase ? '✓' : '○'} One lowercase letter (a-z)
                  </li>
                  <li style={{
                    color: passwordRequirements.hasNumber ? 'var(--success, #28a745)' : 'var(--text-secondary)',
                    marginBottom: '0.25rem'
                  }}>
                    {passwordRequirements.hasNumber ? '✓' : '○'} One number (0-9)
                  </li>
                  <li style={{
                    color: passwordRequirements.hasSymbol ? 'var(--success, #28a745)' : 'var(--text-secondary)',
                    marginBottom: '0.25rem'
                  }}>
                    {passwordRequirements.hasSymbol ? '✓' : '○'} One symbol (!@#$%^&*...)
                  </li>
                </ul>
              </div>
            )}
          </div>
          <div className="form-group">
            <input
              type="password"
              placeholder="Confirm Password"
              value={values.confirmPassword}
              onChange={(e) => handleChange('confirmPassword', e.target.value)}
              onBlur={() => handleBlur('confirmPassword')}
              required
              className={touched.confirmPassword && errors.confirmPassword ? 'error' : ''}
            />
            {touched.confirmPassword && errors.confirmPassword && (
              <span className="error-message">{errors.confirmPassword}</span>
            )}
          </div>
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creating Account...' : 'Sign Up'}
          </button>
        </form>
        <p style={{ marginTop: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Already have an account? <Link to="/login" style={{ color: 'var(--primary)', textDecoration: 'none' }}>Login</Link>
        </p>
      </div>
    </div>
  );
}

export default Signup;
