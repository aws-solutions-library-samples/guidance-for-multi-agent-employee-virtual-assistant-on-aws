import React, { useState, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { sendMessage, getConversationMessages } from '../services/api';
import { useAuth } from '../context/AuthContext';
import FileUploadModal from './FileUploadModal';
import ConversationHistory from './ConversationHistory';

/**
 * Component to render text with clickable links
 */
const MessageText = ({ text }) => {
  if (!text) return null;
  
  // Regular expression to find URLs
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  
  // Find all matches with their positions
  const matches = [];
  let match;
  while ((match = urlRegex.exec(text)) !== null) {
    matches.push({
      url: match[0],
      index: match.index,
      end: match.index + match[0].length
    });
  }
  
  // If no URLs, just return the text
  if (matches.length === 0) {
    return <div style={{ whiteSpace: 'pre-wrap' }}>{text}</div>;
  }
  
  // Build result with links
  const elements = [];
  let lastIndex = 0;
  
  matches.forEach((match, i) => {
    // Add text before the URL
    if (match.index > lastIndex) {
      elements.push(
        <span key={`text-${i}`}>{text.substring(lastIndex, match.index)}</span>
      );
    }
    
    // Add the URL as a link
    elements.push(
      <a 
        key={`link-${i}`}
        href={match.url}
        target="_blank"
        rel="noopener noreferrer"
        style={{ color: '#0972d3', textDecoration: 'underline' }}
      >
        {match.url}
      </a>
    );
    
    lastIndex = match.end;
  });
  
  // Add any remaining text after the last URL
  if (lastIndex < text.length) {
    elements.push(
      <span key={`text-${matches.length}`}>{text.substring(lastIndex)}</span>
    );
  }
  
  return <div style={{ whiteSpace: 'pre-wrap' }}>{elements}</div>;
};

/**
 * Component for displaying AI reasoning steps
 */
const ThinkingStep = ({ steps }) => {
  if (!steps || steps.length === 0) return null;
  
  return (
    <>
      <br />
      <details style={{ marginTop: '8px' }}>
        <summary style={{ cursor: 'pointer', color: '#0066c0', fontWeight: 500 }}>Reasoning Trace</summary>
        <div style={{ marginTop: '8px' }}>
          {steps.map((step, index) => (
            <div key={index} style={{ 
              backgroundColor: '#f0f4f8',
              borderLeft: '3px solid #6c757d', 
              padding: '10px',
              margin: '5px 0',
              fontSize: '0.9em'
            }}>
              <strong>Step {index + 1}:</strong> {step}
            </div>
          ))}
        </div>
      </details>
    </>
  );
};

/**
 * Main chat interface component
 * 
 * Manages the conversation with the AI assistant, sidebar, and file uploads.
 */
const ChatInterface = () => {
  // State management
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [sessionId, setSessionId] = useState(uuidv4());
  const [error, setError] = useState(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [isLoadingConversation, setIsLoadingConversation] = useState(false);
  const { logout } = useAuth();
  
  // DOM references
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  
  // Display initial greeting when component mounts
  useEffect(() => {
    setMessages([{
      role: 'assistant',
      content: "Hello! Welcome to TeamLink AI. I'm here to assist you with any HR, Benefits, IT Support, Learning & Development, or Payroll-related questions. I can also help with AWS blogs, technical guidance, and code artifacts. How can I assist you today?"
    }]);
  }, []);
  
  // Scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);
  
  // Focus input field when component loads
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  /**
   * Starts a new conversation
   */
  const handleNewConversation = () => {
    setSessionId(uuidv4());
    setMessages([{
      role: 'assistant',
      content: "Hello! Welcome to TeamLink AI. I'm here to assist you with any HR, Benefits, IT Support, Learning & Development, or Payroll-related questions. I can also help with AWS blogs, technical guidance, and code artifacts. How can I assist you today?"
    }]);
    setError(null);
  };

  /**
   * Loads an existing conversation by session ID
   * @param {string} selectedSessionId - ID of the session to load
   */
  const handleSelectConversation = async (selectedSessionId) => {
    if (selectedSessionId === sessionId && messages.length > 0) {
      return; // Already showing this conversation
    }
    
    try {
      setIsLoadingConversation(true);
      setError(null);
      
      // Get messages for this conversation
      const conversationMessages = await getConversationMessages(selectedSessionId);
      
      if (!conversationMessages || conversationMessages.length === 0) {
        setError("No messages found for this conversation");
        return;
      }
      
      // Convert the messages to our format
      const formattedMessages = [];
      
      // Process each message
      conversationMessages.forEach(message => {
        // Only add if we have both user query and response
        if (message.userQuery) {
          formattedMessages.push({
            role: 'user',
            content: message.userQuery
          });
        }
        
        if (message.response) {
          formattedMessages.push({
            role: 'assistant',
            content: message.response,
            thinking: message.thinkingSteps || []
          });
        }
      });
      
      // Only update if we have messages to show
      if (formattedMessages.length > 0) {
        setMessages(formattedMessages);
        setSessionId(selectedSessionId);
      } else {
        setError("No valid message content found for this conversation");
      }
      
    } catch (err) {
      setError("Failed to load the conversation: " + err.message);
    } finally {
      setIsLoadingConversation(false);
    }
  };
  
  /**
   * Toggles the sidebar visibility
   */
  const toggleSidebar = () => {
    setShowSidebar(!showSidebar);
  };
  
  /**
   * Sends a message to the AI assistant
   */
  const handleSubmit = async () => {
    const trimmedText = inputText.trim();
    if (!trimmedText || isProcessing) return;
    
    setMessages(prev => [...prev, { role: 'user', content: trimmedText }]);
    setInputText('');
    setIsProcessing(true);
    setError(null);
    
    try {
      const response = await sendMessage(trimmedText, sessionId);
      
      if (response.sessionId) {
        setSessionId(response.sessionId);
      }
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.response,
        thinking: response.thinkingSteps
      }]);
      
    } catch (err) {
      // Format error message
      let errorMessage = "Failed to communicate with the AI assistant";
      
      if (err.message) {
        errorMessage = err.message;
      }
      
      if (err.response) {
        if (err.response.status) {
          errorMessage += ` (Status: ${err.response.status})`;
        }
        
        if (err.response.data) {
          if (typeof err.response.data === 'string') {
            errorMessage = err.response.data;
          } else if (err.response.data.message) {
            errorMessage = err.response.data.message;
          } else if (err.response.data.error) {
            errorMessage += " - " + (typeof err.response.data.error === 'string' ? 
              err.response.data.error : JSON.stringify(err.response.data.error));
          }
        }
      }
      
      setError(errorMessage);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${errorMessage}`
      }]);
    } finally {
      setIsProcessing(false);
      inputRef.current?.focus();
    }
  };
  
  /**
   * Handles key press events in the input field
   * @param {Event} e - Keyboard event
   */
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  /**
   * Handles file upload completion
   * @param {string} folder - Folder where files were uploaded
   * @param {Array} files - Array of uploaded files
   */
  const handleUploadComplete = (folder, files) => {
    const fileNames = files.map(file => file.name).join(", ");
    
    setMessages(prev => [...prev, 
      { 
        role: 'user', 
        content: `I've uploaded ${files.length} file(s) to the ${folder} folder.`
      },
      {
        role: 'assistant',
        content: `Files uploaded successfully to the ${folder} folder: ${fileNames}. The knowledge base will be automatically updated to include this content. You can ask questions about these documents after processing is complete (usually within a few minutes).`
      }
    ]);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Conversation History Sidebar */}
      {showSidebar && (
        <ConversationHistory 
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          currentSessionId={sessionId}
        />
      )}
      
      {/* Main Chat Area */}
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        height: '100vh', 
        overflow: 'hidden',
        flex: 1
      }}>
        {/* Header */}
        <div style={{ 
          position: 'fixed', 
          top: 0, 
          left: showSidebar ? '250px' : '0', 
          right: 0, 
          height: '110px', 
          backgroundColor: 'white', 
          padding: '16px 20px', 
          borderBottom: '1px solid #eaeded', 
          zIndex: 100, 
          boxSizing: 'border-box',
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'flex-start',
          transition: 'left 0.3s' 
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            {/* Sidebar toggle button */}
            <button
              onClick={toggleSidebar}
              style={{
                background: 'none',
                border: 'none',
                fontSize: '24px',
                cursor: 'pointer',
                padding: '4px',
                lineHeight: '1',
                color: '#555',
              }}
              aria-label={showSidebar ? 'Hide conversation history' : 'Show conversation history'}
            >
              {showSidebar ? '←' : '→'}
            </button>
            
            <div>
              <h1 style={{ margin: '0 0 8px 0' }}>🤝 TeamLink AI Assistant</h1>
              <p style={{ margin: 0 }}>Your personal assistant for all employee-related queries</p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={() => setIsUploadModalOpen(true)}
              style={{
                padding: '8px 16px',
                backgroundColor: '#0972d3',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Upload Documents
            </button>
            <button
              onClick={logout}
              style={{
                padding: '8px 16px',
                backgroundColor: 'transparent',
                color: '#0972d3',
                border: '1px solid #0972d3',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Logout
            </button>
          </div>
        </div>
        
        {/* Chat messages area */}
        <div style={{ 
          position: 'fixed', 
          top: '110px', 
          bottom: '120px', 
          left: showSidebar ? '250px' : '0', 
          right: 0, 
          overflowY: 'auto', 
          padding: '20px', 
          backgroundColor: '#f9f9f9', 
          zIndex: 50,
          transition: 'left 0.3s'
        }}>
          
          {/* Loading indicator for conversation */}
          {isLoadingConversation && (
            <div style={{ 
              position: 'absolute', 
              top: 0, 
              left: 0, 
              right: 0, 
              bottom: 0, 
              backgroundColor: 'rgba(255,255,255,0.7)', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              zIndex: 60
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ 
                  width: '40px', 
                  height: '40px', 
                  border: '4px solid #f3f3f3',
                  borderTop: '4px solid #0972d3', 
                  borderRadius: '50%',
                  margin: '0 auto 16px',
                  animation: 'spin 1s linear infinite'
                }}></div>
                <p>Loading conversation...</p>
              </div>
            </div>
          )}
          
          {/* Message bubbles */}
          {messages.map((message, index) => {
            const isUser = message.role === 'user';
            return (
              <div 
                key={index} 
                style={{ 
                  display: 'flex', 
                  justifyContent: isUser ? 'flex-end' : 'flex-start', 
                  marginBottom: '12px', 
                  width: '100%'
                }}
              >
                <div style={{ 
                  backgroundColor: isUser ? '#e1f5fe' : '#f5f5f5', 
                  borderRadius: '18px', 
                  padding: '12px 16px', 
                  width: 'calc(100% - 40px)', 
                  maxWidth: '800px', 
                  boxShadow: '0px 1px 2px rgba(0, 0, 0, 0.1)', 
                  display: 'flex'
                }}>
                  {/* Avatar icon */}
                  <div style={{ 
                    minWidth: '32px', 
                    height: '32px', 
                    borderRadius: '50%', 
                    backgroundColor: isUser ? '#0972d3' : '#414d5c', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    color: 'white', 
                    marginRight: '10px', 
                    paddingTop: '2px'
                  }}>
                    <div style={{ fontSize: '18px', textShadow: '0px 1px 1px rgba(0,0,0,0.2)' }}>
                      {isUser ? '🙋' : '✨'}
                    </div>
                  </div>
                  
                  {/* Message content and thinking steps */}
                  <div style={{ flexGrow: 1 }}>
                    <MessageText text={message.content} />
                    {!isUser && message.thinking && <ThinkingStep steps={message.thinking} />}
                  </div>
                </div>
              </div>
            );
          })}
          
          {/* Loading indicator */}
          {isProcessing && (
            <div style={{ 
              padding: '12px', 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center', 
              gap: '8px', 
              marginBottom: '20px' 
            }}>
              <div style={{ 
                width: '16px', 
                height: '16px', 
                border: '2px solid #f3f3f3', 
                borderTop: '2px solid #3498db', 
                borderRadius: '50%', 
                animation: 'spin 1s linear infinite' 
              }}></div>
              <span>Processing your request...</span>
            </div>
          )}
          
          {/* Error message */}
          {error && (
            <div style={{ 
              padding: '12px', 
              margin: '12px 0', 
              backgroundColor: '#ffebee', 
              border: '1px solid #ffcdd2', 
              borderRadius: '4px', 
              color: '#c62828' 
            }}>
              {error}
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
        
        {/* Input area */}
        <div style={{ 
          position: 'fixed', 
          bottom: 0, 
          left: showSidebar ? '250px' : '0', 
          right: 0, 
          height: '120px', 
          backgroundColor: 'white', 
          padding: '16px 20px', 
          borderTop: '1px solid #eaeded', 
          zIndex: 100, 
          boxSizing: 'border-box', 
          transition: 'left 0.3s'
        }}>
          <textarea
            ref={inputRef}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything about HR, Benefits, IT, Payroll, or AWS tech — I'm here to help!"
            rows={2}
            disabled={isProcessing || isLoadingConversation}
            style={{ 
              width: '100%', 
              padding: '12px 16px', 
              borderRadius: '20px', 
              border: '1px solid #d1d5db', 
              resize: 'none', 
              fontSize: '16px', 
              boxSizing: 'border-box', 
              height: '68px' 
            }}
          />
        </div>

        {/* File Upload Modal */}
        <FileUploadModal
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
          onUploadComplete={handleUploadComplete}
        />
        
        {/* CSS animations */}
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    </div>
  );
};

export default ChatInterface;