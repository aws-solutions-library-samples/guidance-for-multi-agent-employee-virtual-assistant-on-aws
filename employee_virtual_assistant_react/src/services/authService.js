import { Amplify } from 'aws-amplify';
import { 
  signIn as amplifySignIn,
  signUp as amplifySignUp,
  confirmSignUp as amplifyConfirmSignUp,
  signOut as amplifySignOut,
  resetPassword,
  confirmResetPassword,
  getCurrentUser as amplifyGetCurrentUser,
  fetchAuthSession
} from '@aws-amplify/auth';

/**
 * Authentication Service
 * 
 * This service provides authentication functionality using AWS Amplify/Cognito.
 */

/**
 * Configure Amplify Auth with environment variables
 * @returns {Object} Auth configuration
 */
export const configureAuth = () => {
  const region = process.env.REACT_APP_COGNITO_REGION;
  const userPoolId = process.env.REACT_APP_COGNITO_USER_POOL_ID;
  const userPoolClientId = process.env.REACT_APP_COGNITO_CLIENT_ID;
  
  if (!region || !userPoolId || !userPoolClientId) {
    throw new Error('Missing Cognito configuration values in .env file');
  }

  // Amplify v6 uses a different structure for configuration
  const config = {
    Auth: {
      Cognito: {
        region,
        userPoolId,
        userPoolClientId
      }
    }
  };
  
  Amplify.configure(config);
  return config;
};

/**
 * Sign in a user
 * @param {string} username - Username
 * @param {string} password - Password
 * @returns {Promise<Object>} User data if successful
 */
export const signIn = async (username, password) => {
  try {
    const { isSignedIn, nextStep } = await amplifySignIn({ username, password });
    if (isSignedIn) {
      const user = await amplifyGetCurrentUser();
      return user;
    }
    return { isSignedIn, nextStep };
  } catch (error) {
    throw error;
  }
};

/**
 * Sign up a new user
 * @param {string} username - Username
 * @param {string} password - Password
 * @param {string} email - Email address
 * @returns {Promise<Object>} Sign up result
 */
export const signUp = async (username, password, email) => {
  try {
    const { isSignUpComplete, userId, nextStep } = await amplifySignUp({
      username,
      password,
      options: {
        userAttributes: { email }
      }
    });
    
    return { isSignUpComplete, userId, nextStep };
  } catch (error) {
    throw error;
  }
};

/**
 * Confirm sign up with verification code
 * @param {string} username - Username
 * @param {string} code - Verification code
 * @returns {Promise<Object>} Confirmation result
 */
export const confirmSignUp = async (username, code) => {
  try {
    const { isSignUpComplete, nextStep } = await amplifyConfirmSignUp({
      username,
      confirmationCode: code
    });
    return { isSignUpComplete, nextStep };
  } catch (error) {
    throw error;
  }
};

/**
 * Sign out the current user
 * @returns {Promise<boolean>} Success indicator
 */
export const signOut = async () => {
  try {
    await amplifySignOut();
    return true;
  } catch (error) {
    throw error;
  }
};

/**
 * Request password reset
 * @param {string} username - Username
 * @returns {Promise<Object>} Next step information
 */
export const forgotPassword = async (username) => {
  try {
    const { nextStep } = await resetPassword({ username });
    return nextStep;
  } catch (error) {
    throw error;
  }
};

/**
 * Complete password reset
 * @param {string} username - Username
 * @param {string} code - Verification code
 * @param {string} newPassword - New password
 * @returns {Promise<Object>} Next step information
 */
// export const forgotPasswordSubmit = async (username, code, newPassword) => {
//   try {
//     const { nextStep } = await confirmResetPassword({
//       username,
//       confirmationCode: code,
//       newPassword
//     });
//     return nextStep;
//   } catch (error) {
//     throw error;
//   }
// };

export const forgotPasswordSubmit = async (username, code, newPassword) => {
  try {
    // Log what we're doing for debugging
    console.log(`Confirming password reset for user: \${username}`);
    
    // Normalized inputs
    const normalizedUsername = username.trim();
    const normalizedCode = code.trim();
    
    // Call Amplify's confirmResetPassword with proper error handling
    const response = await confirmResetPassword({
      username: normalizedUsername,
      confirmationCode: normalizedCode,
      newPassword
    });
    
    // Log the response to see what's coming back
    console.log("Password reset confirmation response:", response);
    
    // Return a consistent object even if the response is unexpected
    return {
      success: true,
      nextStep: response?.nextStep || { type: 'DONE' }
    };
  } catch (error) {
    console.error("Error confirming password reset:", error);
    
    // Handle specific error cases
    if (error.name === "CodeMismatchException") {
      throw new Error("Invalid verification code. Please check and try again.");
    } else if (error.name === "ExpiredCodeException") {
      throw new Error("The verification code has expired. Please request a new one.");
    } else if (error.name === "InvalidPasswordException") {
      throw new Error("Password doesn't meet requirements. Please use a stronger password.");
    }
    
    // Generic error
    throw new Error(error.message || "Failed to reset password. Please try again.");
  }
};

/**
 * Get current authenticated user
 * @returns {Promise<Object|null>} User data or null if not authenticated
 */
export const getCurrentUser = async () => {
  try {
    const user = await amplifyGetCurrentUser();
    return user;
  } catch (error) {
    return null;
  }
};

/**
 * Get JWT token for API requests
 * @returns {Promise<string|null>} ID token or null
 */
export const getJwtToken = async () => {
  try {
    const { tokens } = await fetchAuthSession();
    return tokens?.idToken?.toString() || null;
  } catch (error) {
    return null;
  }
};