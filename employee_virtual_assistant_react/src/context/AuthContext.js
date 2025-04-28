import React, { createContext, useState, useEffect, useContext } from 'react';
import { getCurrentUser, signOut, getJwtToken } from '../services/authService';

// Create the authentication context
const AuthContext = createContext(null);

/**
 * Authentication Provider Component
 * 
 * Manages authentication state throughout the application.
 */
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check authentication status on component mount
    const checkUser = async () => {
      try {
        const userData = await getCurrentUser();
        
        if (userData) {
          // Try to get the JWT token and extract user ID from it
          const token = await getJwtToken();
          
          if (token) {
            try {
              // Decode the token to extract the subject (user ID)
              const tokenParts = token.split('.');
              if (tokenParts.length === 3) {
                const base64 = tokenParts[1].replace(/-/g, '+').replace(/_/g, '/');
                const jsonPayload = decodeURIComponent(atob(base64).split('')
                  .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
                  .join(''));
                
                const tokenData = JSON.parse(jsonPayload);
                if (tokenData.sub) {
                  const enhancedUserData = {
                    ...userData,
                    userId: tokenData.sub
                  };
                  setUser(enhancedUserData);
                  return;
                }
              }
            } catch (e) {
              // Fallback if token parsing fails
              console.error('Error decoding token');
            }
          }
          
          // Fallback to username if token extraction failed
          setUser({
            ...userData,
            userId: userData.username || 'anonymous'
          });
        } else {
          setUser(null);
        }
      } catch (error) {
        console.error('Error checking authentication');
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
  
    checkUser();
  }, []);

  /**
   * Set user data after successful login
   * @param {Object} userData - User data from authentication
   */
  const login = (userData) => {
    // Try to extract userId from various possible locations
    const userId = 
      userData?.attributes?.sub || 
      userData?.signInDetails?.loginId || 
      userData?.username || 
      userData?.userId || 
      'anonymous';
    
    // Enhanced user data with userId
    const enhancedUserData = {
      ...userData,
      userId: userId
    };
    
    setUser(enhancedUserData);
  };

  /**
   * Sign out the current user
   */
  const logout = async () => {
    try {
      await signOut();
      setUser(null);
    } catch (error) {
      console.error('Error signing out');
    }
  };

  // Provide the authentication context to child components
  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

/**
 * Custom hook to use the authentication context
 * @returns {Object} Authentication context
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};