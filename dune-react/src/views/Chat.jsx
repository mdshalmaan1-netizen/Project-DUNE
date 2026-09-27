import React, { useState, useEffect, useRef } from 'react';
import { useStore } from '../store/useStore';
import { formatMarkdown } from '../utils/helpers';
import { getGeminiApiKey } from '../services/aiEngine';

export default function Chat() {
  const {
    state,
    isAiTyping,
    sendChatMessage,
    sendQuickChat,
    updateApiKey,
    createNewChat,
    selectConversation,
    deleteConversation,
    downloadFile,
    downloadTextAsFile,
    handleFileUpload,
    showToast
  } = useStore();

  const [inputVal, setInputVal] = useState('');
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [inputKeyVal, setInputKeyVal] = useState('');
  const [isHistoryOpen, setIsHistoryOpen] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const messagesEndRef = useRef(null);

  const activeApiKey = getGeminiApiKey(state);
  const isGeminiActive = Boolean(activeApiKey);

  const conversations = state.conversations || [];
  const activeConv = conversations.find(c => c.id === state.activeConversationId) || conversations[0];
  const messages = activeConv ? (activeConv.messages || []) : (state.chatHistory || []);

  const userName = (state.user.name || '').trim()
    ? state.user.name.split(' ')[0]
    : 'there';

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isAiTyping]);

  const handleSend = () => {
    const text = inputVal.trim();
    if (!text) return;
    setInputVal('');
    sendChatMessage(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  const triggerUpload = () => {
    const input = document.getElementById('doc-file-input');
    if (input) input.click();
  };

  const handleSaveApiKey = (e) => {
    e.preventDefault();
    updateApiKey(inputKeyVal.trim());
    setShowKeyModal(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const activeDoc = state.files && state.files.length > 0 ? state.files[0] : null;

  return (
    <section id="view-chat" className="view-section active">
      <div id="chat-view-container">
        <div
          className={`chat-layout-wrapper ${isDragging ? 'dragging-active' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >

          {/* ================= LEFT: CHATGPT-STYLE CHAT HISTORY SIDEBAR ================= */}
          <aside className={`chat-history-sidebar ${isHistoryOpen ? '' : 'collapsed'}`}>
            <div className="chat-history-header">
              <button className="btn-new-chat" onClick={createNewChat}>
                <span>✨</span> + New Chat
              </button>
              <div className="chat-history-title-row">
                <span>Recent Chats ({conversations.length})</span>
                <button
                  className="btn-del-conv"
                  style={{ opacity: 0.8, fontSize: '14px', cursor: 'pointer' }}
                  onClick={() => setIsHistoryOpen(false)}
                  title="Collapse History Sidebar"
                >
                  ◀
                </button>
              </div>
            </div>

            <div className="chat-history-list">
              {conversations.map(conv => {
                const isActive = conv.id === (activeConv ? activeConv.id : null);
                return (
                  <div
                    key={conv.id}
                    className={`chat-history-item ${isActive ? 'active' : ''}`}
                    onClick={() => selectConversation(conv.id)}
                  >
                    <div className="chat-history-item-content">
                      <span className="chat-history-icon">💬</span>
                      <div className="chat-history-text-wrap">
                        <div className="chat-history-item-title" title={conv.title}>
                          {conv.title || 'New Conversation'}
                        </div>
                        <div className="chat-history-item-date">
                          {conv.createdAt || 'Today'}
                        </div>
                      </div>
                    </div>
                    <button
                      className="btn-del-conv"
                      title="Delete chat"
                      onClick={(e) => deleteConversation(conv.id, e)}
                    >
                      🗑️
                    </button>
                  </div>
                );
              })}
            </div>
          </aside>

          {/* ================= RIGHT: MAIN CHAT PANEL ================= */}
          <div className="chat-main-area">
            {/* Chat Top Header */}
            <div className="chat-header-bar">
              <div className="chat-header-info">
                {!isHistoryOpen && (
                  <button
                    className="btn-toggle-history"
                    onClick={() => setIsHistoryOpen(true)}
                    title="Open Chat History"
                  >
                    <span>📜</span>
                    <span>History ({conversations.length})</span>
                  </button>
                )}
                <div className="chat-mascot-avatar">
                  <img
                    src="/assets/dune_logo.jpg"
                    alt="DUNE Avatar"
                    onError={(e) => { e.currentTarget.src = 'https://api.iconify.design/fluent-emoji:robot.svg'; }}
                  />
                </div>
                <div className="chat-title-text">
                  <h3>{activeConv?.title || 'Chat with DUNE'}</h3>
                  <p>ChatGPT-Style AI • English, Tamil & Tanglish Mastery • Multi-turn Memory</p>
                </div>
              </div>
              <div className="chat-quick-chips">
                <button
                  className="chip-btn"
                  style={{ background: 'var(--primary-light)', color: 'var(--primary-dark)', borderColor: '#fbcfe8' }}
                  onClick={createNewChat}
                  title="Start a new blank conversation"
                >
                  ➕ New Chat
                </button>
                <button className="chip-btn" onClick={() => sendQuickChat('What is my schedule for today?')}>
                  My Schedule
                </button>
                <button className="chip-btn" onClick={() => sendQuickChat('What are my upcoming deadlines?')}>
                  Upcoming Deadlines
                </button>
                <button className="chip-btn" onClick={() => sendQuickChat('Summarize key points from my uploaded files')}>
                  Summarize Notes
                </button>
              </div>
            </div>

            {/* Gemini Integration Status Banner */}
            <div style={{
              margin: '10px 20px 0',
              padding: '8px 16px',
              borderRadius: '10px',
              background: isGeminiActive
                ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(99, 102, 241, 0.08) 100%)'
                : 'linear-gradient(135deg, rgba(255, 75, 130, 0.1) 0%, rgba(168, 85, 247, 0.1) 100%)',
              border: isGeminiActive ? '1px solid rgba(16, 185, 129, 0.25)' : '1px solid rgba(255, 75, 130, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '8px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '15px' }}>{isGeminiActive ? '⚡' : '✨'}</span>
                <div>
                  <div style={{ fontSize: '12.5px', fontWeight: 700, color: isGeminiActive ? '#059669' : '#be123c' }}>
                    {isGeminiActive ? 'Google Gemini Live AI Connected' : 'Connect Google Gemini AI for Real Answers'}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {isGeminiActive
                      ? 'Speaks fluent Tanglish, English & Tamil. Deep document reading, coding & reasoning active.'
                      : 'Get natural conversational intelligence, Tanglish chat, song lyrics, and answers to any question.'}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button
                  className="btn-show-actions"
                  style={{
                    padding: '4px 10px',
                    fontSize: '11px',
                    background: isGeminiActive ? '#ffffff' : 'var(--primary-gradient)',
                    color: isGeminiActive ? '#059669' : '#ffffff',
                    border: isGeminiActive ? '1px solid #10b981' : 'none',
                    boxShadow: isGeminiActive ? 'none' : '0 2px 8px rgba(255,75,130,0.3)',
                    cursor: 'pointer'
                  }}
                  onClick={() => {
                    setInputKeyVal(state.user.apiKey || '');
                    setShowKeyModal(true);
                  }}
                >
                  {isGeminiActive ? '⚙️ Manage API Key' : '🔑 Connect Free Gemini Key'}
                </button>
                {!isGeminiActive && (
                  <a
                    href="https://aistudio.google.com/app/apikey"
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontSize: '11px', color: 'var(--primary)', textDecoration: 'underline', fontWeight: 600 }}
                  >
                    Get Free Key ↗
                  </a>
                )}
              </div>
            </div>

            {/* Active Document Analysis & Quick Q&A Bar */}
            {activeDoc && (
              <div style={{
                margin: '8px 20px 0',
                padding: '9px 14px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(238, 242, 255, 0.95) 0%, rgba(245, 243, 255, 0.95) 100%)',
                border: '1px solid rgba(199, 210, 254, 0.8)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '180px' }}>
                  <span style={{ fontSize: '18px' }}>📑</span>
                  <div>
                    <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#312e81' }}>
                      Active Document: {activeDoc.name}
                    </div>
                    <div style={{ fontSize: '11px', color: '#6366f1' }}>
                      Deeply analyzed & ready for Q&A ({state.files.length} document{state.files.length > 1 ? 's' : ''} available)
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="chip-btn"
                    style={{ fontSize: '11px', padding: '4px 10px', background: '#fff', border: '1px solid #c7d2fe', color: '#4338ca', fontWeight: 600 }}
                    onClick={() => sendQuickChat(`In "${activeDoc.name}", which college or university is mentioned, what degree/course, and what are all education details?`)}
                  >
                    🎓 College & Education
                  </button>
                  <button
                    type="button"
                    className="chip-btn"
                    style={{ fontSize: '11px', padding: '4px 10px', background: '#fff', border: '1px solid #c7d2fe', color: '#4338ca', fontWeight: 600 }}
                    onClick={() => sendQuickChat(`What are the key technical skills and tools mentioned in "${activeDoc.name}"?`)}
                  >
                    🛠️ Skills
                  </button>
                  <button
                    type="button"
                    className="chip-btn"
                    style={{ fontSize: '11px', padding: '4px 10px', background: '#fff', border: '1px solid #c7d2fe', color: '#4338ca', fontWeight: 600 }}
                    onClick={() => sendQuickChat(`What work experience and projects are listed in "${activeDoc.name}"?`)}
                  >
                    💼 Projects & Experience
                  </button>
                  <button
                    type="button"
                    className="chip-btn"
                    style={{ fontSize: '11px', padding: '4px 10px', background: '#fff', border: '1px solid #c7d2fe', color: '#4338ca', fontWeight: 600 }}
                    onClick={() => sendQuickChat(`Provide a comprehensive analysis and summary of "${activeDoc.name}".`)}
                  >
                    📋 Full Summary
                  </button>
                </div>
              </div>
            )}

            {/* Messages Log */}
            <div className="chat-messages-box" id="chat-messages-container">
              {messages.length === 0 ? (
                <div style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '40px 20px',
                  textAlign: 'center',
                  color: 'var(--text-muted)'
                }}>
                  <div style={{
                    width: '60px',
                    height: '60px',
                    borderRadius: '18px',
                    background: 'var(--primary-soft-gradient)',
                    border: '1.5px solid #fbcfe8',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '14px',
                    boxShadow: '0 6px 18px rgba(255, 75, 130, 0.12)'
                  }}>
                    <img
                      src="/assets/dune_logo.jpg"
                      alt="DUNE"
                      style={{ width: '38px', height: '38px', objectFit: 'contain' }}
                      onError={(e) => { e.currentTarget.src = 'https://api.iconify.design/fluent-emoji:robot.svg'; }}
                    />
                  </div>
                  <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                    What can I help with today?
                  </h3>
                  <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', maxWidth: '420px', lineHeight: 1.5 }}>
                    Ask anything in <strong>English, Tamil, or Tanglish</strong> — song lyrics, code, assignments, or daily conversations.
                  </p>
                </div>
              ) : (
                messages.map((msg, idx) => {
                  // Check for [DOWNLOAD:filename] tags
                  const downloadRegex = /\[DOWNLOAD:\s*(.+?)\]/gi;
                  const downloadTags = [];
                  let match;
                  while ((match = downloadRegex.exec(msg.text || '')) !== null) {
                    downloadTags.push(match[1].trim());
                  }
                  const cleanDisplayText = (msg.text || '').replace(/\[DOWNLOAD:\s*(.+?)\]/gi, '').trim();

                  return (
                    <div key={idx} className={`chat-msg-row ${msg.role}`}>
                      {msg.role === 'ai' && (
                        <div className="chat-msg-avatar ai">
                          <img
                            src="/assets/dune_logo.jpg"
                            alt="DUNE"
                            onError={(e) => { e.currentTarget.src = 'https://api.iconify.design/fluent-emoji:robot.svg'; }}
                          />
                        </div>
                      )}
                      <div className="chat-bubble">
                        {msg.role === 'ai' ? (
                          <div className="ai-msg-block">
                            <div dangerouslySetInnerHTML={{ __html: formatMarkdown(cleanDisplayText) }} />

                            {/* Render interactive 1-click Download Card for shared/requested files */}
                            {downloadTags.length > 0 && (
                              <div className="download-cards-container">
                                {downloadTags.map((targetName, tagIdx) => {
                                  const matchedFile = (state.files || []).find(f =>
                                    f.name.toLowerCase() === targetName.toLowerCase() ||
                                    f.name.toLowerCase().includes(targetName.toLowerCase()) ||
                                    targetName.toLowerCase().includes(f.name.toLowerCase().replace(/\.[^/.]+$/, ""))
                                  );

                                  if (matchedFile) {
                                    return (
                                      <div key={tagIdx} className="file-download-card">
                                        <div className="file-download-card-icon">
                                          {matchedFile.name.endsWith('.pdf') ? '📕' : '📄'}
                                        </div>
                                        <div className="file-download-card-info">
                                          <div className="file-download-card-title">{matchedFile.name}</div>
                                          <div className="file-download-card-meta">
                                            {matchedFile.type || 'DOCUMENT'} • {matchedFile.date || 'My Files'}
                                          </div>
                                        </div>
                                        <button
                                          type="button"
                                          className="btn-download-card-action"
                                          onClick={() => downloadFile(matchedFile)}
                                          title={`Download ${matchedFile.name}`}
                                        >
                                          <span>📥</span> Download File
                                        </button>
                                      </div>
                                    );
                                  }

                                  // AI Generated note/file
                                  return (
                                    <div key={tagIdx} className="file-download-card generated">
                                      <div className="file-download-card-icon">📝</div>
                                      <div className="file-download-card-info">
                                        <div className="file-download-card-title">{targetName}</div>
                                        <div className="file-download-card-meta">AI Generated Study Material</div>
                                      </div>
                                      <button
                                        type="button"
                                        className="btn-download-card-action"
                                        onClick={() => downloadTextAsFile(targetName, cleanDisplayText)}
                                        title={`Download ${targetName}`}
                                      >
                                        <span>📥</span> Download Note
                                      </button>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Subtle Copy button & Action Confirmation */}
                            <div className="chat-msg-actions">
                              <button
                                type="button"
                                className="btn-chat-action"
                                onClick={() => {
                                  navigator.clipboard?.writeText(cleanDisplayText);
                                  showToast('Response copied!', '📋');
                                }}
                                title="Copy text"
                              >
                                📋 Copy
                              </button>
                            </div>

                            {msg.actionExecuted && (
                              <div style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                background: 'rgba(16, 185, 129, 0.08)',
                                border: '1px solid rgba(16, 185, 129, 0.25)',
                                color: '#059669',
                                fontSize: '12px',
                                fontWeight: '600',
                                padding: '4px 10px',
                                borderRadius: '8px',
                                marginTop: '8px'
                              }}>
                                <span>⚡</span>
                                <span>{msg.actionExecuted}</span>
                              </div>
                            )}
                          </div>
                        ) : (
                          msg.text
                        )}
                        {msg.citation && (
                          <div className="citation-tag">📄 {msg.citation}</div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}

              {isAiTyping && (
                <div className="chat-msg-row ai">
                  <div className="chat-msg-avatar ai">
                    <img
                      src="/assets/dune_logo.jpg"
                      alt="DUNE"
                      onError={(e) => { e.currentTarget.src = 'https://api.iconify.design/fluent-emoji:robot.svg'; }}
                    />
                  </div>
                  <div className="chat-bubble" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    {isGeminiActive ? 'DUNE is thinking with Google Gemini...' : 'DUNE is typing...'}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Chat Input Area */}
            <div className="chat-input-bar-wrap">
              <button
                type="button"
                className="btn-icon-soft"
                title="Upload Document or Notes to Chat"
                onClick={triggerUpload}
              >
                📎
              </button>
              <div className="chat-input-box">
                <input
                  type="text"
                  id="chat-user-input"
                  value={inputVal}
                  onChange={(e) => setInputVal(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={isGeminiActive ? "Message DUNE (Tanglish, Tamil, English, Code, Songs, Notes)..." : "Ask DUNE anything about your classes, uploaded PDFs, or study tasks..."}
                />
              </div>
              <button
                type="button"
                className="btn-send-round"
                onClick={handleSend}
                title="Send Message"
              >
                ➤
              </button>
            </div>
          </div>

        </div>
      </div>

      {/* Quick Gemini API Key Setup Modal */}
      {showKeyModal && (
        <div className="modal-overlay active" style={{ zIndex: 1100 }}>
          <div className="modal-box">
            <button className="modal-close-btn" type="button" onClick={() => setShowKeyModal(false)}>✕</button>
            <h3 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-main)', marginBottom: '8px' }}>
              <span>🔑</span> Connect Google Gemini AI
            </h3>
            <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginBottom: '16px', lineHeight: 1.5 }}>
              Enable real, unrestricted Google Gemini intelligence for answering any question, generating code, speaking Tanglish, writing songs, and tutoring you on your coursework.
            </p>

            <form onSubmit={handleSaveApiKey}>
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label>Google Gemini API Key</label>
                <input
                  type="password"
                  value={inputKeyVal}
                  onChange={(e) => setInputKeyVal(e.target.value)}
                  placeholder="Paste your AI Studio API key here (AIzaSy...)"
                  autoFocus
                />
              </div>

              <div style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '10px',
                padding: '10px 12px',
                marginBottom: '18px',
                fontSize: '12px',
                color: '#475569'
              }}>
                <strong>How to get a 100% Free Key in 30 seconds:</strong>
                <ol style={{ margin: '6px 0 0 16px', padding: 0 }}>
                  <li>Go to <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" style={{ color: 'var(--primary)', fontWeight: 600 }}>Google AI Studio</a>.</li>
                  <li>Click <strong>"Create API key"</strong>.</li>
                  <li>Copy and paste the key here. (Free, no credit card needed).</li>
                </ol>
              </div>

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn-show-actions"
                  style={{ background: '#f1f5f9', color: 'var(--text-main)', boxShadow: 'none' }}
                  onClick={() => setShowKeyModal(false)}
                >
                  Cancel
                </button>
                {inputKeyVal && (
                  <button
                    type="button"
                    className="btn-show-actions"
                    style={{ background: '#fee2e2', color: '#ef4444', boxShadow: 'none' }}
                    onClick={() => {
                      updateApiKey('');
                      setShowKeyModal(false);
                    }}
                  >
                    Remove Key
                  </button>
                )}
                <button type="submit" className="btn-action-primary">
                  Save & Activate Gemini
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
