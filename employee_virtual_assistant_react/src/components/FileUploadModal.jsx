import React, { useState, useEffect } from 'react';
import { getJwtToken } from '../services/authService';
import axios from 'axios';

/**
 * FileUploadModal component
 * 
 * Modal for uploading documents to specific knowledge domains.
 * 
 * @param {Object} props
 * @param {boolean} props.isOpen - Controls modal visibility
 * @param {Function} props.onClose - Called when modal is closed
 * @param {Function} props.onUploadComplete - Called when upload is successful
 */
const FileUploadModal = ({ isOpen, onClose, onUploadComplete }) => {
  // Available folders for document categorization
  const folders = ['HR', 'IT Helpdesk', 'Benefits', 'Payroll', 'Training'];
  const allowedFileTypes = ['.pdf', '.doc', '.docx'];

  // Get API endpoint from environment variables
  const API_ENDPOINT = process.env.REACT_APP_FILE_UPLOAD_ENDPOINT || 
                      (process.env.REACT_APP_API_GATEWAY_ENDPOINT ? 
                        process.env.REACT_APP_API_GATEWAY_ENDPOINT.replace('/invoke', '') + '/upload' 
                        : '');

  // Component state
  const [selectedFolder, setSelectedFolder] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState(null);
  
  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedFolder('');
      setSelectedFiles([]);
      setUploadProgress(0);
      setError(null);
    }
  }, [isOpen]);
  
  // Don't render anything if modal is closed
  if (!isOpen) return null;
  
  /**
   * Handle folder selection
   */
  const handleFolderChange = (e) => {
    setSelectedFolder(e.target.value);
  };
  
  /**
   * Handle file selection
   */
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files);
    
    // Validate file types
    const invalidFiles = files.filter(file => {
      const extension = '.' + file.name.split('.').pop().toLowerCase();
      return !allowedFileTypes.includes(extension);
    });
    
    if (invalidFiles.length > 0) {
      setError(`Only ${allowedFileTypes.join(', ')} files are allowed.`);
      return;
    }
    
    setSelectedFiles(files);
    setError(null);
  };
  
  /**
   * Convert a file to base64 format
   * @param {File} file - File to convert
   * @returns {Promise<string>} - Base64 representation of the file
   */
  const readFileAsBase64 = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };
  
  /**
   * Upload files to the server
   */
  const uploadFiles = async () => {
    try {
      setIsUploading(true);
      setUploadProgress(0);
      
      // Get authentication token
      const token = await getJwtToken();
      
      // Process files to base64
      const processedFiles = await Promise.all(selectedFiles.map(async file => {
        return {
          name: file.name,
          type: file.type,
          content: await readFileAsBase64(file)
        };
      }));

      setUploadProgress(30);
      
      // Send to API
      const response = await axios.post(
        API_ENDPOINT, 
        {
          folder: selectedFolder,
          files: processedFiles
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
          }
        }
      );
      
      setUploadProgress(100);
      
      // Notify parent component about successful upload
      onUploadComplete(selectedFolder, selectedFiles);
      
      // Close modal after a short delay
      setTimeout(() => onClose(), 1000);
    } catch (err) {
      let errorMessage = 'Upload failed';
      if (err.response && err.response.data && err.response.data.message) {
        errorMessage = err.response.data.message;
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setIsUploading(false);
    }
  };
  
  /**
   * Handle form submission
   */
  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (!selectedFolder) {
      setError('Please select a folder');
      return;
    }
    
    if (selectedFiles.length === 0) {
      setError('Please select at least one file');
      return;
    }
    
    uploadFiles();
  };
  
  return (
    <div className="modal-overlay" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    }}>
      <div className="modal-content" style={{
        backgroundColor: 'white',
        borderRadius: '8px',
        padding: '20px',
        width: '500px',
        maxWidth: '90%',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      }}>
        <h2 style={{ marginTop: 0 }}>Upload Documents</h2>
        
        {error && (
          <div style={{ 
            backgroundColor: '#ffebee', 
            color: '#c62828', 
            padding: '10px', 
            borderRadius: '4px', 
            marginBottom: '15px' 
          }}>
            {error}
          </div>
        )}
        
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '15px' }}>
            <label htmlFor="folder" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Select Folder:
            </label>
            <select 
              id="folder" 
              value={selectedFolder} 
              onChange={handleFolderChange}
              style={{ 
                width: '100%', 
                padding: '10px', 
                borderRadius: '4px',
                border: '1px solid #d1d5db'
              }}
              disabled={isUploading}
            >
              <option value="">Select a folder</option>
              {folders.map((folder) => (
                <option key={folder} value={folder}>{folder}</option>
              ))}
            </select>
          </div>
          
          <div style={{ marginBottom: '15px' }}>
            <label htmlFor="files" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
              Select Files:
            </label>
            <input 
              id="files" 
              type="file" 
              multiple
              accept=".pdf,.doc,.docx"
              onChange={handleFileChange}
              style={{ display: 'block', width: '100%' }}
              disabled={isUploading}
            />
            <small style={{ color: '#666', marginTop: '5px', display: 'block' }}>
              Allowed file types: PDF, DOC, DOCX
            </small>
          </div>
          
          {selectedFiles.length > 0 && (
            <div style={{ marginBottom: '15px' }}>
              <p style={{ fontWeight: 'bold', marginBottom: '5px' }}>Selected Files:</p>
              <ul style={{ margin: 0, paddingLeft: '20px' }}>
                {selectedFiles.map((file, index) => (
                  <li key={index}>{file.name}</li>
                ))}
              </ul>
            </div>
          )}
          
          {isUploading && (
            <div style={{ marginBottom: '15px' }}>
              <div style={{ 
                height: '10px', 
                backgroundColor: '#e0e0e0', 
                borderRadius: '5px',
                overflow: 'hidden'
              }}>
                <div style={{ 
                  height: '100%', 
                  width: uploadProgress + '%', 
                  backgroundColor: '#0972d3',
                  transition: 'width 0.3s ease'
                }} />
              </div>
              <p style={{ textAlign: 'center', margin: '5px 0 0' }}>
                {`Uploading... ${uploadProgress}%`}
              </p>
            </div>
          )}
          
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              style={{
                padding: '10px 15px',
                backgroundColor: 'transparent',
                color: '#0972d3',
                border: '1px solid #0972d3',
                borderRadius: '4px',
                cursor: isUploading ? 'default' : 'pointer',
                opacity: isUploading ? 0.7 : 1,
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isUploading || !selectedFolder || selectedFiles.length === 0}
              style={{
                padding: '10px 15px',
                backgroundColor: '#0972d3',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: (isUploading || !selectedFolder || selectedFiles.length === 0) ? 'default' : 'pointer',
                opacity: (isUploading || !selectedFolder || selectedFiles.length === 0) ? 0.7 : 1,
              }}
            >
              {isUploading ? 'Uploading...' : 'Upload Files'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default FileUploadModal;