import React, { useState, useEffect } from 'react';
import { getConversationHistory } from '../services/api';

/**
 * ConversationHistory component
 * 
 * Displays the sidebar with conversation history and allows creating
 * new conversations or selecting existing ones.
 * 
 * @param {Object} props
 * @param {Function} props.onSelectConversation - Callback when a conversation is selected
 * @param {Function} props.onNewConversation - Callback to create a new conversation
 * @param {string} props.currentSessionId - Current active session ID
 */
const ConversationHistory = ({ onSelectConversation, onNewConversation, currentSessionId }) => {
  const [conversations, setConversations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    fetchConversations();
  }, []);

  useEffect(() => {
    // Refresh the conversation list when a new conversation is started
    // or if the currentSessionId changes
    if (currentSessionId) {
      fetchConversations();
    }
  }, [currentSessionId]);
  
  /**
   * Fetches conversation history from the API
   */
  const fetchConversations = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const history = await getConversationHistory();
      setConversations(history);
    } catch (err) {
      setError(`Failed to load history: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };
  
  /**
   * Formats a timestamp for display
   * @param {string} timestamp - Timestamp in YYYY-MM-DD HH:MM:SS format
   * @returns {string} Formatted date/time string
   */
  const formatDate = (timestamp) => {
    try {
      // Parse the timestamp (YYYY-MM-DD HH:MM:SS format)
      const date = new Date(timestamp.replace(' ', 'T') + 'Z');
      
      // If today, show time only
      const today = new Date();
      if (date.toDateString() === today.toDateString()) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      }
      
      // If this year, show month and day
      if (date.getFullYear() === today.getFullYear()) {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      }
      
      // Otherwise show full date
      return date.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' });
    } catch (e) {
      return timestamp;
    }
  };
  
  return (
    <div style={{
      width: '250px',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      borderRight: '1px solid #eaeded',
      backgroundColor: '#f7f7f7'
    }}>
      {/* Header */}
      <div style={{
        padding: '16px',
        borderBottom: '1px solid #eaeded',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h3 style={{ margin: 0 }}>Conversations</h3>
        <button
          onClick={onNewConversation}
          style={{
            backgroundColor: '#0972d3',
            color: 'white',
            border: 'none',
            borderRadius: '50%',
            width: '32px',
            height: '32px',
            fontSize: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer'
          }}
          aria-label="New conversation"
        >
          +
        </button>
      </div>
      
      {/* Loading state */}
      {isLoading && (
        <div style={{ padding: '16px', textAlign: 'center' }}>
          <div style={{ 
            width: '24px', 
            height: '24px', 
            border: '3px solid #f3f3f3',
            borderTop: '3px solid #0972d3', 
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto'
          }}></div>
          <p style={{ marginTop: '8px' }}>Loading conversations...</p>
        </div>
      )}
      
      {/* Error state */}
      {error && !isLoading && (
        <div style={{ padding: '16px', color: '#d13212', textAlign: 'center' }}>
          <p>{error}</p>
          <button
            onClick={fetchConversations}
            style={{
              backgroundColor: '#0972d3',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              padding: '8px 12px',
              cursor: 'pointer'
            }}
          >
            Retry
          </button>
        </div>
      )}
      
      {/* Empty state */}
      {!isLoading && !error && conversations.length === 0 && (
        <div style={{ padding: '16px', textAlign: 'center', color: '#666' }}>
          <p>No previous conversations</p>
        </div>
      )}
      
      {/* Conversation list */}
      {!isLoading && !error && conversations.length > 0 && (
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {conversations.map((conversation) => (
          <div 
            key={conversation.sessionId}
            onClick={() => onSelectConversation(conversation.sessionId)}
            style={{
              padding: '12px 16px',
              borderBottom: '1px solid #eaeded',
              cursor: 'pointer',
              backgroundColor: currentSessionId === conversation.sessionId ? '#e6f2ff' : 'transparent',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              transition: 'background-color 0.3s'
            }}
            onMouseOver={(e) => {
              if (currentSessionId !== conversation.sessionId) {
                e.currentTarget.style.backgroundColor = '#f0f0f0';
              }
            }}
            onMouseOut={(e) => {
              if (currentSessionId !== conversation.sessionId) {
                e.currentTarget.style.backgroundColor = 'transparent';
              }
            }}
          >
            {/* Message content - using more space */}
            <div style={{ 
              fontSize: '14px',
              color: '#333',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              flex: 1,
              marginRight: '8px'
            }}>
              {conversation.latestMessage || '(No messages)'}
            </div>
            
            {/* Timestamp only */}
            <div style={{ 
              fontSize: '12px',
              color: '#666',
              whiteSpace: 'nowrap'
            }}>
              {formatDate(conversation.timestamp)}
            </div>
          </div>
        ))}
      </div>
    )}
    </div>
  );
};

export default ConversationHistory;