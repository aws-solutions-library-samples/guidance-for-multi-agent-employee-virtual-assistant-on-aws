import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { signIn } from '../../services/authService';
import { useAuth } from '../../context/AuthContext';

/**
 * Login component
 * 
 * Handles user authentication using Cognito.
 */
const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  /**
   * Handle form submission
   * @param {Event} e - Form submit event
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const result = await signIn(username, password);
      login(result);
      navigate('/');
    } catch (err) {
      setError(err.message || 'Failed to log in. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '400px', margin: '0 auto', padding: '20px' }}>
      <h2 style={{ marginBottom: '20px', textAlign: 'center' }}>Login to TeamLink AI</h2>

      {error && (
        <div style={{ 
          backgroundColor: '#ffebee', 
          color: '#c62828', 
          padding: '10px', 
          borderRadius: '4px', 
          marginBottom: '20px' 
        }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <div>
          <label htmlFor="username" style={{ display: 'block', marginBottom: '5px' }}>
            Username
          </label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            style={{ 
              width: '100%', 
              padding: '10px', 
              borderRadius: '4px', 
              border: '1px solid #d1d5db' 
            }}
          />
        </div>

        <div>
          <label htmlFor="password" style={{ display: 'block', marginBottom: '5px' }}>
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{ 
              width: '100%', 
              padding: '10px', 
              borderRadius: '4px', 
              border: '1px solid #d1d5db' 
            }}
          />
        </div>

        <button
          type="submit"
          disabled={isLoading}
          style={{
            padding: '12px',
            backgroundColor: '#0972d3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isLoading ? 'default' : 'pointer',
            opacity: isLoading ? 0.7 : 1,
          }}
        >
          {isLoading ? 'Logging in...' : 'Login'}
        </button>
      </form>

      <div style={{ marginTop: '20px', textAlign: 'center' }}>
        <p>
          Don't have an account?{' '}
          <Link to="/signup" style={{ color: '#0972d3', textDecoration: 'none' }}>
            Sign up
          </Link>
        </p>
        <p>
          <Link to="/forgot-password" style={{ color: '#0972d3', textDecoration: 'none' }}>
            Forgot password?
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Login;