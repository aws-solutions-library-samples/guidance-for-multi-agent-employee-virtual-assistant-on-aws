import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import '@cloudscape-design/global-styles/index.css';

// Components
import ChatInterface from './components/ChatInterface';
import Login from './components/auth/Login';
import SignUp from './components/auth/SignUp';
import ConfirmSignUp from './components/auth/ConfirmSignUp';
import ForgotPassword from './components/auth/ForgotPassword';
import AuthLayout from './components/auth/AuthLayout';
import ProtectedRoute from './components/common/ProtectedRoute';

// Context and Services
import { AuthProvider } from './context/AuthContext';
import { configureAuth } from './services/authService';

// Initialize auth configuration
try {
  configureAuth();
} catch (err) {
  console.warn('Auth configuration warning:', err);
}

/**
 * Main application component
 * 
 * Sets up routing and authentication for the application.
 */
function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Auth routes */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<SignUp />} />
            <Route path="/confirm-signup" element={<ConfirmSignUp />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
          </Route>
          
          {/* Protected routes */}
          <Route 
            path="/" 
            element={
              <ProtectedRoute>
                <ChatInterface />
              </ProtectedRoute>
            } 
          />
          
          {/* Catch all other routes */}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;