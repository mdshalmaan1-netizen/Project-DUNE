import React, { useState } from 'react';
import { useStore } from '../../store/useStore';

export default function Header() {
  const { state, openNewTaskModal, switchView, sendQuickChat } = useStore();
  const [searchValue, setSearchValue] = useState('');

  const name = (state.user.name || '').trim();
  const greetingTitle = name ? `Good day, ${name.split(' ')[0]}! 🌸` : 'Welcome to DUNE! 🌸';
  const greetingSubtitle = state.user.university
    ? `${state.user.university} • AI Academic Companion`
    : 'Your personal student AI workspace is ready.';

  const urgentTasksCount = state.tasks.filter(t => !t.completed && t.priority === 'high').length;

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      const q = searchValue.trim();
      if (q) {
        sendQuickChat(q);
        setSearchValue('');
      }
    }
  };

  return (
    <header className="app-header">
      <div className="header-greeting">
        <h2 id="header-greeting-title">{greetingTitle}</h2>
        <p id="header-greeting-subtitle">{greetingSubtitle}</p>
      </div>

      <div className="header-search-bar">
        <span className="search-icon">🔍</span>
        <input
          type="text"
          id="global-search-input"
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask DUNE anything... (e.g. check schedule, explain a topic)"
        />
      </div>

      <div className="header-actions">
        <button className="btn-action-primary" onClick={openNewTaskModal}>
          <span>➕</span> New Task
        </button>
        <button className="btn-icon-soft" onClick={() => switchView('risk')} title="Risk Notifications">
          <span>🔔</span>
          {urgentTasksCount > 0 && <div className="notification-dot" id="header-alert-dot"></div>}
        </button>
        <button className="btn-icon-soft" onClick={() => switchView('settings')} title="Settings & API Key">
          <span>⚙️</span>
        </button>
      </div>
    </header>
  );
}
