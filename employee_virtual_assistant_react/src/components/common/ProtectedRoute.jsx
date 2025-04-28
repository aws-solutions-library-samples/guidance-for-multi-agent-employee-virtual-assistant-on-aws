import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

/**
 * ProtectedRoute component
 * 
 * A route wrapper that redirects to login if the user is not authenticated.
 * Shows a loading spinner while checking authentication status.
 * 
 * @param {Object} props - Component props
 * @param {React.ReactNode} props.children - Child components to render when authenticated
 */
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  // Show loading indicator while checking auth state
  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh' 
      }}>
        <div style={{ 
          width: '40px', 
          height: '40px', 
          border: '5px solid #f3f3f3',
          borderTop: '5px solid #0972d3', 
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }}></div>
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!user) {
    return <Navigate to="/login" />;
  }

  // Render the protected content if authenticated
  return children;
};

export default ProtectedRoute;