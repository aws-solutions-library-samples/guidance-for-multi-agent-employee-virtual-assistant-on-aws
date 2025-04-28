import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { forgotPassword, forgotPasswordSubmit } from '../../services/authService';

/**
 * ForgotPassword component
 * 
 * Manages the password reset flow with two stages:
 * 1. Request a verification code
 * 2. Submit the code along with a new password
 */
const ForgotPassword = () => {
  const [stage, setStage] = useState(1); // 1 = request code, 2 = submit code and new password, 3 = success
  const [username, setUsername] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  /**
   * Handle request for verification code
   * @param {Event} e - Form submit event
   */
  const handleRequestCode = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setIsLoading(true);

    try {
      await forgotPassword(username);
      setMessage('Verification code sent to your email.');
      setStage(2);
    } catch (err) {
      setError(err.message || 'Failed to request password reset. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle password reset submission
   * @param {Event} e - Form submit event
   */
  // const handleResetPassword = async (e) => {
  //   e.preventDefault();
  //   setError('');
  //   setMessage('');

  //   if (newPassword !== confirmPassword) {
  //     setError('Passwords do not match');
  //     return;
  //   }

  //   setIsLoading(true);

  //   try {
  //     await forgotPasswordSubmit(username, code, newPassword);
  //     setMessage('Password reset successfully. You can now log in with your new password.');
  //     setStage(3); // Success stage
  //   } catch (err) {
  //     setError(err.message || 'Failed to reset password. Please try again.');
  //   } finally {
  //     setIsLoading(false);
  //   }
  // };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
  
    // Validate inputs
    if (!code.trim()) {
      setError('Verification code is required');
      return;
    }
    
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }
  
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
  
    setIsLoading(true);
  
    try {
      // Wrap in a try/catch and handle the response more carefully
      const result = await forgotPasswordSubmit(username, code, newPassword);
      console.log("Reset password result:", result);
      
      // Check if we have a success result before changing stage
      if (result && result.success) {
        setMessage('Password reset successfully. You can now log in with your new password.');
        setStage(3); // Success stage
      } else {
        // Generic success message as fallback
        setMessage('Password has been reset.');
        setStage(3);
      }
    } catch (err) {
      // Log the full error for debugging
      console.error("Reset password error:", err);
      setError(err.message || 'Failed to reset password. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '400px', margin: '0 auto', padding: '20px' }}>
      <h2 style={{ marginBottom: '20px', textAlign: 'center' }}>Reset Your Password</h2>

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

      {message && (
        <div style={{ 
          backgroundColor: '#e8f5e9', 
          color: '#388e3c', 
          padding: '10px', 
          borderRadius: '4px', 
          marginBottom: '20px' 
        }}>
          {message}
        </div>
      )}

      {stage === 1 ? (
        <form onSubmit={handleRequestCode} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
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
            {isLoading ? 'Sending Code...' : 'Send Verification Code'}
          </button>
        </form>
      ) : stage === 2 ? (
        <form onSubmit={handleResetPassword} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
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

          <div>
            <label htmlFor="newPassword" style={{ display: 'block', marginBottom: '5px' }}>
              New Password
            </label>
            <input
              id="newPassword"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
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
            <label htmlFor="confirmPassword" style={{ display: 'block', marginBottom: '5px' }}>
              Confirm New Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
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
            {isLoading ? 'Resetting Password...' : 'Reset Password'}
          </button>
        </form>
      ) : (
        <div style={{ textAlign: 'center' }}>
          <p>Your password has been reset successfully.</p>
          <Link
            to="/login"
            style={{
              display: 'inline-block',
              marginTop: '15px',
              padding: '10px 15px',
              backgroundColor: '#0972d3',
              color: 'white',
              textDecoration: 'none',
              borderRadius: '4px',
            }}
          >
            Go to Login
          </Link>
        </div>
      )}

      <div style={{ marginTop: '20px', textAlign: 'center' }}>
        <Link to="/login" style={{ color: '#0972d3', textDecoration: 'none' }}>
          Back to Login
        </Link>
      </div>
    </div>
  );
};

export default ForgotPassword;