import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { confirmSignUp } from '../../services/authService';

/**
 * ConfirmSignUp component
 * 
 * Handles the account confirmation process after signup.
 * Users enter the verification code sent to their email.
 */
const ConfirmSignUp = () => {
  const [username, setUsername] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Extract username from query parameters
    const params = new URLSearchParams(location.search);
    const usernameParam = params.get('username');
    
    if (usernameParam) {
      setUsername(usernameParam);
    }
  }, [location.search]);

  /**
   * Handle form submission
   * @param {Event} e - Form submit event
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await confirmSignUp(username, code);
      navigate('/login', { 
        state: { message: 'Account confirmed successfully. Please log in.' } 
      });
    } catch (err) {
      setError(err.message || 'Failed to confirm signup. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '400px', margin: '0 auto', padding: '20px' }}>
      <h2 style={{ marginBottom: '20px', textAlign: 'center' }}>Confirm Your Account</h2>
      <p style={{ marginBottom: '20px', textAlign: 'center' }}>
        Please enter the verification code sent to your email.
      </p>

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
          <label htmlFor="code" style={{ display: 'block', marginBottom: '5px' }}>
            Verification Code
          </label>
          <input
            id="code"
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
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
          {isLoading ? 'Confirming...' : 'Confirm'}
        </button>
      </form>

      <div style={{ marginTop: '20px', textAlign: 'center' }}>
        <p>
          <Link to="/login" style={{ color: '#0972d3', textDecoration: 'none' }}>
            Back to Login
          </Link>
        </p>
      </div>
    </div>
  );
};

export default ConfirmSignUp;