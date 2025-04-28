import { render, screen } from '@testing-library/react';
import App from './App';

// Mock the AuthProvider to avoid auth issues in tests
jest.mock('./context/AuthContext', () => ({
  AuthProvider: ({ children }) => <div>{children}</div>,
  useAuth: () => ({ user: null, loading: false })
}));

// Mock the auth service
jest.mock('./services/authService', () => ({
  configureAuth: jest.fn()
}));

test('renders without crashing', () => {
  render(<App />);
  // App should render without throwing any errors
});