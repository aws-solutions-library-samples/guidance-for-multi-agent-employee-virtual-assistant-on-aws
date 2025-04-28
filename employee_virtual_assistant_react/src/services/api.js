import axios from 'axios';
import { getJwtToken } from './authService';

/**
 * API Service for communicating with the backend
 * 
 * This service handles all API calls to the Employee Virtual Assistant backend.
 */

/**
 * Send a message to the AI assistant
 * 
 * @param {string} message - User's message
 * @param {string} sessionId - Session ID for conversation tracking
 * @returns {Promise<Object>} - Response from the AI assistant
 */
export const sendMessage = async (message, sessionId) => {
  try {
    // Get JWT token for authenticated requests
    const token = await getJwtToken();
    
    const headers = {
      'Content-Type': 'application/json'
    };
    
    // Add authorization if token exists
    if (token) {
      headers['Authorization'] = 'Bearer ' + token;
    }
    
    const response = await axios.post(
      process.env.REACT_APP_API_GATEWAY_ENDPOINT, 
      { message, sessionId }, 
      { headers }
    );
    
    return response.data;
  } catch (error) {
    console.error('API Error:', {
      message: error.message,
      response: error.response?.data || 'No response data',
      status: error.response?.status || 'No status code'
    });
    throw new Error(error.response?.data?.error || 'Failed to communicate with the AI assistant');
  }
};

/**
 * Get conversation history for the current user
 * 
 * @param {number} limit - Maximum number of conversations to return
 * @returns {Promise<Array>} - List of conversation summaries
 */
export const getConversationHistory = async (limit = 20) => {
  try {
    const token = await getJwtToken();
    
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    
    // Use environment variable for history endpoint
    const apiUrl = process.env.REACT_APP_HISTORY_ENDPOINT;
    
    const response = await axios.get(apiUrl, { 
      headers,
      params: { limit }
    });
    
    return response.data.conversations || [];
  } catch (error) {
    console.error('Error fetching conversation history:', error);
    throw error;
  }
};

/**
 * Get messages for a specific conversation session
 * 
 * @param {string} sessionId - Session ID to get messages for
 * @returns {Promise<Array>} - List of messages in the conversation
 */
export const getConversationMessages = async (sessionId) => {
  try {
    const token = await getJwtToken();
    
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    
    // Use environment variable with fallback
    let baseApiUrl = process.env.REACT_APP_MESSAGES_ENDPOINT;
    if (!baseApiUrl) {
      console.warn('REACT_APP_MESSAGES_ENDPOINT not set in environment');
      // Only use fallback in development
      baseApiUrl = process.env.NODE_ENV === 'development' 
        ? 'http://localhost:3001/messages' 
        : '/api/messages';
    }
    
    // Clean the URL and add session ID
    if (baseApiUrl.endsWith('/')) baseApiUrl = baseApiUrl.slice(0, -1);
    const apiUrl = baseApiUrl + '/' + sessionId;
    
    const response = await axios.get(apiUrl, { headers });
    return response.data.messages || [];
  } catch (error) {
    console.error('Error fetching messages:', error);
    throw error;
  }
};