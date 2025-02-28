import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './App.css';

// Map model names to display names
const getDisplayName = (modelName) => {
  const modelMap = {
    'mistral:latest': 'Mistral',
    'deepseek-r1:latest': 'DeepSeek R1',
    'llama3.2:latest': 'Llama 3.2',
    'gemma2:2b': 'Gemma 2',
  };

  // Check for known models
  for (const key in modelMap) {
    if (modelName.toLowerCase().includes(key.toLowerCase())) {
      return modelMap[key];
    }
  }

  // For other models, try to extract and format the name
  const parts = modelName.split(':');
  if (parts.length > 0) {
    // Capitalize first letter of each word
    return parts[0].split(/[^a-zA-Z0-9]/).map(word => 
      word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    ).join(' ');
  }
  
  return modelName;
};

function App() {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentResponse, setCurrentResponse] = useState('');
  const [initialConnectionMade, setInitialConnectionMade] = useState(false);
  const [chatHistories, setChatHistories] = useState([]);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  
  const socketRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Define components for code blocks with syntax highlighting
  const markdownComponents = {
    code({node, inline, className, children, ...props}) {
      const match = /language-(\w+)/.exec(className || '');
      return !inline && match ? (
        <SyntaxHighlighter
          style={vscDarkPlus}
          language={match[1]}
          PreTag="div"
          {...props}
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      ) : (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
  };
  const loadChatHistory = (historyId) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: 'load_history',
        history_id: historyId
      }));
      setShowHistoryModal(false);
    }
  };
  
  // Add a function to fetch chat histories
  const fetchChatHistories = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/chat_histories?model=${selectedModel}`);
      const data = await response.json();
      setChatHistories(data.histories);
    } catch (error) {
      console.error('Error fetching chat histories:', error);
    }
  };

  // Load available models when component mounts
  useEffect(() => {
    fetchModels();
  }, []);

  // Scroll to bottom of messages when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages, currentResponse]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Fetch available models from Python backend
  const fetchModels = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/models');
      const data = await response.json();
      const models = data.models.reverse();
      if (data.models && data.models.length > 0) {
        setModels(models);
        // Select the first model by default
        setSelectedModel(models[0]);
      }
    } catch (error) {
      console.error('Error fetching models:', error);
      setMessages(prev => [
        ...prev,
        { type: 'system', content: 'Error connecting to the server. Please ensure the backend is running.' }
      ]);
    }
  };

  // Effect for handling the end of streaming
  useEffect(() => {
    if (!isStreaming && currentResponse) {
      setMessages(prev => [
        ...prev, 
        { type: 'assistant', content: currentResponse, model: selectedModel }
      ]);
      setCurrentResponse('');
    }
  }, [isStreaming, currentResponse, selectedModel]);

  // Connect to WebSocket when a model is selected
  useEffect(() => {
    if (selectedModel) {
      // Close existing socket connection if any
      if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.close();
      }
  
      // Create new WebSocket connection
      const socket = new WebSocket(`ws://localhost:8000/ws/${selectedModel}`);
      
      socket.onopen = () => {
        console.log(`Connected to ${selectedModel} WebSocket`);
        setIsConnected(true);

        if (!initialConnectionMade) {
          setMessages(prev => [
            ...prev,
            { 
              type: 'assistant', 
              content: `Hello there! I am ${getDisplayName(selectedModel)}. How can I assist you today?`,
              model: selectedModel 
            }
          ]);
          setInitialConnectionMade(true);
        }
      };
      
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'stream_start') {
            setIsStreaming(true);
            setCurrentResponse('');
          } 
          else if (data.type === 'stream') {
            setCurrentResponse(prev => prev + data.content);
          } 
          else if (data.type === 'stream_end') {
            setIsStreaming(false);
          } 
          else if (data.type === 'error') {
            setIsStreaming(false);
            setMessages(prev => [
              ...prev,
              { 
                type: 'system', 
                content: `Error: ${data.content}` 
              }
            ]);
          }
          else if (data.type === 'chat_histories') {
            // Store available chat histories
            setChatHistories(data.histories);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };   
      
      socket.onclose = () => {
        console.log(`Disconnected from ${selectedModel} WebSocket`);
        setIsConnected(false);
      };
      
      socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      };
      
      socketRef.current = socket;
      
      // Clean up socket when component unmounts or model changes
      return () => {
        if (socket.readyState === WebSocket.OPEN) {
          socket.close();
        }
      };
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedModel]);

  // Handle model change
  const handleModelChange = (e) => {
    setSelectedModel(e.target.value);
  };

  // Handle send message
  const handleSendMessage = (e) => {
    e.preventDefault();
    
    if (!inputMessage.trim() || !isConnected || isStreaming) return;
    
    // Add user message to chat
    setMessages(prev => [
      ...prev, 
      { type: 'user', content: inputMessage }
    ]);
    
    // Send message to WebSocket
    socketRef.current.send(JSON.stringify({
      type: 'message',
      content: inputMessage
    }));
    
    // Clear input
    setInputMessage('');
  };

  return (
    <div className="app-container">
      <div className="sidebar">
        <h2>Ollama Assistants</h2>
        <div className="model-selector">
          <label htmlFor="model-select">SELECT MODEL:</label>
          <select 
            id="model-select" 
            value={selectedModel} 
            onChange={handleModelChange}
            disabled={isStreaming}
          >
            {models.map(model => (
              <option key={model} value={model}>
                {getDisplayName(model)}
              </option>
            ))}
          </select>
        </div>
        
        {/* System status messages now in the sidebar */}
        <div className="application-status">
          <h3>Application Status</h3>
          <div className="status-detail">
            <span>Model:</span>
            <span>{getDisplayName(selectedModel)}</span>
          </div>
          <div className="status-detail">
            <span>Status:</span>
            <span>
              <span className={`connection-dot ${isConnected ? 'connection-dot-green' : 'connection-dot-red'}`}></span>
              <span className={isConnected ? 'status-green' : 'status-red'}>
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </span>
          </div>
        </div>
      </div>
      
      <div className="chat-container">
        <div className="messages-container">
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.type}`}>
              <div className="message-header">
                {message.type === 'user' ? 'You' : 
                 message.type === 'assistant' ? getDisplayName(message.model) : 'System'}
              </div>
              <div className="message-content">
                {message.type === 'assistant' ? (
                  <ReactMarkdown components={markdownComponents}>
                    {message.content}
                  </ReactMarkdown>
                ) : (
                  message.content
                )}
              </div>
            </div>
          ))}
          
          {isStreaming && (
            <div className="message assistant">
              <div className="message-header">{getDisplayName(selectedModel)}</div>
              <div className="message-content">
                <ReactMarkdown components={markdownComponents}>
                  {currentResponse}
                </ReactMarkdown>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
        
        <form className="input-container" onSubmit={handleSendMessage}>
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Type your message here..."
            disabled={!isConnected || isStreaming}
          />
          <button 
            type="submit" 
            disabled={!isConnected || isStreaming || !inputMessage.trim()}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;