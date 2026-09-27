import React from 'react';
import { useStore } from '../../store/useStore';

export default function Sidebar() {
  const { state, activeView, switchView } = useStore();

  const activeTasksCount = state.tasks.filter(t => !t.completed).length;
  const urgentTasksCount = state.tasks.filter(t => !t.completed && t.priority === 'high').length;
  const filesCount = state.files.length;

  const name = (state.user.name || '').trim();
  const initials = name
    ? name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase()
    : 'U';
  const userTag = state.user.major
    ? `${state.user.semester ? state.user.semester + ' • ' : ''}${state.user.major}`
    : 'Click to configure';

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'chat', label: 'Chat with DUNE', icon: '💬', badge: { text: 'AI', className: 'nav-badge info' } },
    {
      id: 'files',
      label: 'My Files',
      icon: '📁',
      badge: filesCount > 0 ? {
        text: filesCount,
        className: 'nav-badge',
        style: { display: 'inline-block', background: '#f1f5f9', color: 'var(--text-muted)' }
      } : null
    },
    { id: 'calendar', label: 'Calendar', icon: '📅' },
    {
      id: 'tasks',
      label: 'Tasks',
      icon: '✅',
      badge: activeTasksCount > 0 ? {
        text: activeTasksCount,
        className: 'nav-badge',
        style: { display: 'inline-block' }
      } : null
    },
    { id: 'timetable', label: 'Timetable', icon: '🕒' },
    { id: 'insights', label: 'Insights', icon: '📈' },
    {
      id: 'risk',
      label: 'Risk Alerts',
      icon: '⚠️',
      badge: urgentTasksCount > 0 ? {
        text: urgentTasksCount,
        className: 'nav-badge',
        style: { display: 'inline-block' }
      } : null
    },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ];

  return (
    <aside id="sidebar">
      <div className="brand-section" onClick={() => switchView('dashboard')} role="button" tabIndex={0}>
        <div className="brand-logo-container">
          <img
            src="/assets/dune_logo.jpg"
            alt="DUNE Logo"
            className="brand-logo-img"
            onError={(e) => { e.currentTarget.src = 'https://api.iconify.design/fluent-emoji:robot.svg'; }}
          />
        </div>
        <div className="brand-title-wrap">
          <span className="brand-title">DUNE</span>
          <span className="brand-subtitle">Personal AI Assistant</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map(item => {
          const isActive = activeView === item.id;
          return (
            <div
              key={item.id}
              className={`nav-item ${isActive ? 'active' : ''}`}
              data-view={item.id}
              onClick={() => switchView(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
              {item.badge && (
                <span className={item.badge.className} style={item.badge.style}>
                  {item.badge.text}
                </span>
              )}
            </div>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="user-profile-card" onClick={() => switchView('settings')}>
          <div className="user-avatar" id="sidebar-user-avatar">
            {initials}
            <div className="status-dot"></div>
          </div>
          <div className="user-info">
            <span className="user-name" id="sidebar-user-name">
              {name || 'Your Profile'}
            </span>
            <span className="user-tag" id="sidebar-user-tag">
              {userTag}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}
