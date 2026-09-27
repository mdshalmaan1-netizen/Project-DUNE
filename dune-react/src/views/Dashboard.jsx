import React from 'react';
import { useStore } from '../store/useStore';
import EmptyState from '../components/EmptyState';

export default function Dashboard() {
  const {
    state,
    switchView,
    openNewTaskModal,
    openAddScheduleModal,
    handleDashboardActionClick
  } = useStore();

  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const todayStr = days[new Date().getDay()];
  const todayClasses = state.schedule.filter(s => s.day === todayStr);

  const activeTasks = state.tasks.filter(t => !t.completed);
  const totalTasks = state.tasks.length;
  const completedTasks = state.tasks.filter(t => t.completed).length;
  const healthScore = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 100;
  const donutOffset = 264 - (264 * healthScore / 100);

  // Banner text & button
  let bannerText = '';
  let actionBtnText = '';
  if (activeTasks.length > 0) {
    const topTask = activeTasks[0];
    bannerText = `Focus Next: "${topTask.title}" (Due: ${topTask.due}). Ready for a 30-min focus session?`;
    actionBtnText = 'Start Focus Session';
  } else if (state.files.length === 0) {
    bannerText = 'Upload your syllabus or lecture slides to enable automatic summaries, exam prep, and quizzes.';
    actionBtnText = '+ Upload Course File';
  } else {
    bannerText = 'All pending tasks completed. Ask DUNE in chat to quiz you on your uploaded files!';
    actionBtnText = 'Open Chat with DUNE';
  }

  return (
    <section id="view-dashboard" className="view-section active">
      {/* 4 Stats Cards */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-content">
            <h4>Classes Today</h4>
            <div className="stat-number" id="stat-classes-today">
              {todayClasses.length}
            </div>
            <span className="stat-badge-sub" id="stat-classes-sub">
              {todayClasses.length > 0
                ? `Next: ${todayClasses[0].title} (${todayClasses[0].time})`
                : 'No classes scheduled'}
            </span>
          </div>
          <div className="stat-icon-wrap pink">📚</div>
        </div>

        <div className="stat-card">
          <div className="stat-content">
            <h4>Active Tasks</h4>
            <div className="stat-number" id="stat-tasks-active">
              {activeTasks.length}
            </div>
            <span className="stat-badge-sub" id="stat-tasks-sub">
              {activeTasks.length} Pending
            </span>
          </div>
          <div className="stat-icon-wrap purple">📝</div>
        </div>

        <div className="stat-card">
          <div className="stat-content">
            <h4>Documents Indexed</h4>
            <div className="stat-number" id="stat-docs-count">
              {state.files.length}
            </div>
            <span className="stat-badge-sub" id="stat-docs-sub">
              {state.files.length} Files Indexed
            </span>
          </div>
          <div className="stat-icon-wrap amber">📑</div>
        </div>

        <div className="stat-card">
          <div className="stat-content">
            <h4>AI Engine Status</h4>
            <div className="stat-number" style={{ fontSize: '20px', color: '#10b981' }}>
              Active ⚡
            </div>
            <span className="stat-badge-sub" style={{ color: '#10b981' }}>
              Precision Mode
            </span>
          </div>
          <div className="stat-icon-wrap emerald">🧠</div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="dashboard-grid">
        {/* Left Column: Schedule & Deadlines */}
        <div className="dash-col-left">
          {/* Today's Schedule */}
          <div className="dash-card">
            <div className="card-header-flex">
              <h3><span>📅</span> Today's Schedule</h3>
              <button
                className="btn-show-actions"
                style={{ padding: '4px 12px', fontSize: '11px' }}
                onClick={openAddScheduleModal}
              >
                + Add Class
              </button>
            </div>
            <div className="schedule-list" id="dash-schedule-list">
              {todayClasses.length === 0 ? (
                <EmptyState
                  icon="📅"
                  title={`No Classes for Today (${todayStr})`}
                  desc="Add your timetable or lecture slots to track your daily schedule."
                  actionLabel="+ Add Class"
                  onAction={openAddScheduleModal}
                  actionClassName="btn-show-actions"
                />
              ) : (
                todayClasses.map(c => (
                  <div key={c.id} className="schedule-item">
                    <span className="schedule-time">{c.time}</span>
                    <div className="schedule-details">
                      <div className="schedule-name">{c.title}</div>
                      <div className="schedule-room">{c.room || 'Classroom'}</div>
                    </div>
                    <span className="badge-pill">Scheduled</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Upcoming Deadlines */}
          <div className="dash-card">
            <div className="card-header-flex">
              <h3><span>⏳</span> Upcoming Deadlines</h3>
              <a className="card-link" onClick={() => switchView('tasks')} role="button" tabIndex={0}>
                View all tasks →
              </a>
            </div>
            <div className="deadlines-list" id="dash-deadlines-list">
              {activeTasks.length === 0 ? (
                <EmptyState
                  icon="✨"
                  title="No Pending Deadlines"
                  desc="You're all caught up! Add a new task to stay organized."
                  actionLabel="+ New Task"
                  onAction={openNewTaskModal}
                  actionClassName="btn-show-actions"
                />
              ) : (
                activeTasks.slice(0, 4).map(t => (
                  <div key={t.id} className="deadline-row">
                    <div>
                      <div className="deadline-name">{t.title}</div>
                      <div className="deadline-date">Due: {t.due}</div>
                    </div>
                    <span className={`badge-pill priority-${t.priority}`}>
                      {t.priority.toUpperCase()}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: What should I do now & Academic Health */}
        <div className="dash-col-right">
          {/* Next Action Banner */}
          <div className="next-action-banner">
            <h3><span>✨</span> What should I do right now?</h3>
            <p id="dash-action-banner-text">{bannerText}</p>
            <button
              className="btn-show-actions"
              id="dash-action-btn"
              onClick={handleDashboardActionClick}
            >
              {actionBtnText}
            </button>
          </div>

          {/* Academic Health */}
          <div className="dash-card">
            <div className="card-header-flex">
              <h3><span>🩺</span> Academic Health</h3>
              <span
                className="badge-pill"
                id="health-status-badge"
                style={{
                  background: healthScore >= 70 ? '#ecfdf5' : '#fef3c7',
                  color: healthScore >= 70 ? '#059669' : '#d97706',
                  fontWeight: 700
                }}
              >
                {healthScore >= 70 ? 'Good' : 'Needs Attention'}
              </span>
            </div>
            <div className="health-card-body">
              <div className="health-donut">
                <svg viewBox="0 0 100 100">
                  <circle className="donut-bg" cx="50" cy="50" r="42"></circle>
                  <circle
                    className="donut-fill"
                    id="health-donut-circle"
                    cx="50"
                    cy="50"
                    r="42"
                    style={{ strokeDashoffset: donutOffset }}
                  ></circle>
                </svg>
                <div className="donut-percent" id="health-score-val">
                  {healthScore}%
                </div>
              </div>
              <div className="health-desc">
                <h4 id="health-desc-title">
                  {healthScore === 100 ? 'Clean Slate' : healthScore >= 70 ? 'On Track' : 'Pending Work'}
                </h4>
                <p id="health-desc-text">
                  {healthScore === 100
                    ? 'You have no overdue assignments or conflicting exam schedules.'
                    : `${completedTasks} of ${totalTasks} tasks finished.`}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
