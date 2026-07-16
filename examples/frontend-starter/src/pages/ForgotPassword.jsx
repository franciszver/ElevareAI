import { Link } from 'react-router-dom';
import './Login.css';

function ForgotPassword() {
  return (
    <div className="login">
      <div className="login-container">
        <img src="/elevare-logo.svg" alt="ElevareAI" style={{ width: '80px', height: '80px', marginBottom: '1rem' }} />
        <h1>Forgot Password</h1>
        <p style={{ marginBottom: '2rem', color: 'var(--text-secondary)' }}>
          Password reset is unavailable in this demo. Contact the administrator.
        </p>
        <p style={{ textAlign: 'center' }}>
          <Link to="/login" style={{ color: 'var(--primary)', textDecoration: 'none' }}>
            Back to Login
          </Link>
        </p>
      </div>
    </div>
  );
}

export default ForgotPassword;
