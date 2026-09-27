import React from 'react';
import { useStore } from './store/useStore';
import Sidebar from './components/Layout/Sidebar';
import Header from './components/Layout/Header';
import Toast from './components/Toast';
import TaskModal from './components/Modals/TaskModal';
import ScheduleModal from './components/Modals/ScheduleModal';

import Dashboard from './views/Dashboard';
import Chat from './views/Chat';
import Files from './views/Files';
import Calendar from './views/Calendar';
import Tasks from './views/Tasks';
import Timetable from './views/Timetable';
import Insights from './views/Insights';
import RiskAlerts from './views/RiskAlerts';
import Settings from './views/Settings';

export default function App() {
  const { activeView, handleFileUpload } = useStore();

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileUpload(file);
      e.target.value = '';
    }
  };

  const renderActiveView = () => {
    switch (activeView) {
      case 'dashboard':
        return <Dashboard />;
      case 'chat':
        return <Chat />;
      case 'files':
        return <Files />;
      case 'calendar':
        return <Calendar />;
      case 'tasks':
        return <Tasks />;
      case 'timetable':
        return <Timetable />;
      case 'insights':
        return <Insights />;
      case 'risk':
        return <RiskAlerts />;
      case 'settings':
        return <Settings />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <>
      <div className="ambient-blush"></div>
      <div className="ambient-blush-left"></div>

      {/* SVG Gradient definition for Donut Chart */}
      <svg style={{ width: 0, height: 0, position: 'absolute' }} aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id="donutGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ff4b82" />
            <stop offset="100%" stopColor="#a855f7" />
          </linearGradient>
        </defs>
      </svg>

      <div id="app-container">
        <Sidebar />
        <main id="main-content">
          <Header />
          <div className="view-content-wrapper">
            {renderActiveView()}
          </div>
        </main>
      </div>

      <TaskModal />
      <ScheduleModal />
      <Toast />

      {/* Hidden file input for document indexing */}
      <input
        type="file"
        id="doc-file-input"
        accept=".pdf,.doc,.docx,.txt"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
    </>
  );
}
