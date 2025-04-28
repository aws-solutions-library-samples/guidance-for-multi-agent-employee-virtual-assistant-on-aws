import React from 'react';
import { Outlet } from 'react-router-dom';

/**
 * Layout component for authentication pages
 * 
 * Provides a consistent layout for login, signup, and other auth-related pages.
 */
const AuthLayout = () => {
  return (
    <div style={{ 
      display: 'flex', 
      minHeight: '100vh', 
      alignItems: 'center', 
      justifyContent: 'center', 
      backgroundColor: '#f9f9f9' 
    }}>
      <div style={{ 
        width: '450px', 
        backgroundColor: 'white', 
        borderRadius: '8px', 
        boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)', 
        padding: '30px' 
      }}>
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <h1 style={{ margin: 0, color: '#0972d3' }}>🤝 TeamLink AI</h1>
          <p style={{ margin: '10px 0 0 0', color: '#666' }}>
            Your personal assistant for all employee-related queries
          </p>
        </div>
        <Outlet />
      </div>
    </div>
  );
};

export default AuthLayout;