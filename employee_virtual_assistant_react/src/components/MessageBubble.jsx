import React from 'react';

/**
 * MessageBubble component
 * 
 * Displays a chat message bubble with thinking steps if applicable.
 * 
 * @param {Object} props
 * @param {Object} props.message - The message object to display
 * @param {boolean} props.isUser - Whether the message is from the user
 */
const MessageBubble = ({ message, isUser }) => {
  if (!message) return null;
  
  return (
    <div
      style={{ 
        padding: '12px 16px',
        backgroundColor: isUser ? '#e1f5fe' : '#f5f5f5',
        borderRadius: '18px',
        marginBottom: '10px',
        marginLeft: isUser ? 'auto' : '0',
        marginRight: isUser ? '0' : 'auto',
        maxWidth: '80%',
        boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)'
      }}
    >
      <div style={{ whiteSpace: 'pre-wrap' }}>{message.content}</div>
      
      {/* Display thinking steps if available (and not user message) */}
      {!isUser && message.thinking && message.thinking.length > 0 && (
        <div style={{ marginTop: '8px' }}>
          <details>
            <summary style={{ cursor: 'pointer', color: '#0066c0', fontWeight: 500 }}>
              See reasoning
            </summary>
            <div style={{ marginTop: '8px' }}>
              {message.thinking.map((step, index) => (
                <div 
                  key={index}
                  style={{
                    backgroundColor: '#f0f4f8',
                    borderLeft: '3px solid #6c757d',
                    padding: '10px',
                    margin: '5px 0',
                    fontSize: '0.9em'
                  }}
                >
                  <strong>Step {index + 1}:</strong> {step}
                </div>
              ))}
            </div>
          </details>
        </div>
      )}
    </div>
  );
};

export default MessageBubble;