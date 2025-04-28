import React from 'react';

/**
 * ThinkingStep component
 * 
 * Displays the AI's reasoning steps in a collapsible section.
 * 
 * @param {Object} props
 * @param {Array} props.steps - Array of reasoning step strings
 */
const ThinkingStep = ({ steps }) => {
  if (!steps || steps.length === 0) return null;
  
  return (
    <div style={{ marginTop: '10px' }}>
      <details>
        <summary style={{ cursor: 'pointer', color: '#0066c0', fontWeight: 500 }}>
          See reasoning process
        </summary>
        
        <div style={{ marginTop: '8px' }}>
          {steps.map((step, index) => (
            <div 
              key={index}
              className="thinking-step"
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
  );
};

export default ThinkingStep;