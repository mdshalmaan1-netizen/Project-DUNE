import React from 'react';
import { useStore } from '../store/useStore';

export default function Tasks() {
  const { state, openNewTaskModal, toggleTaskStatus, deleteTask } = useStore();

  const highTasks = state.tasks.filter(t => t.priority === 'high');
  const medTasks = state.tasks.filter(t => t.priority === 'med');
  const lowTasks = state.tasks.filter(t => t.priority === 'low');

  const renderTaskCategory = (taskList, emptyMsg) => {
    if (taskList.length === 0) {
      return (
        <div style={{ fontSize: '12.5px', color: 'var(--text-dim)', padding: '10px 0' }}>
          {emptyMsg}
        </div>
      );
    }

    return taskList.map(t => (
      <div key={t.id} className="task-interactive-row">
        <div className="task-left-check">
          <input
            type="checkbox"
            className="task-checkbox"
            checked={t.completed}
            onChange={() => toggleTaskStatus(t.id)}
          />
          <span
            className="task-label"
            style={t.completed ? { textDecoration: 'line-through', color: 'var(--text-dim)' } : {}}
          >
            {t.title}
          </span>
        </div>
        <div className="task-right-actions">
          <span className={`badge-pill priority-${t.priority}`}>Due: {t.due}</span>
          <button
            className="btn-del-task"
            title="Delete Task"
            onClick={() => deleteTask(t.id)}
          >
            ✕
          </button>
        </div>
      </div>
    ));
  };

  return (
    <section id="view-tasks" className="view-section active">
      <div className="tasks-header-bar">
        <h2>Academic Tasks & Priorities</h2>
        <button className="btn-action-primary" onClick={openNewTaskModal}>
          <span>➕</span> New Task
        </button>
      </div>

      {/* High Priority */}
      <div className="tasks-priority-card">
        <div className="priority-sec-title high">
          <span>🔴</span> High Priority (<span id="task-count-high">{highTasks.length}</span>)
        </div>
        <div className="tasks-table-list" id="tasks-list-high">
          {renderTaskCategory(highTasks, 'No high priority tasks')}
        </div>
      </div>

      {/* Medium Priority */}
      <div className="tasks-priority-card">
        <div className="priority-sec-title med">
          <span>🟡</span> Medium Priority (<span id="task-count-med">{medTasks.length}</span>)
        </div>
        <div className="tasks-table-list" id="tasks-list-med">
          {renderTaskCategory(medTasks, 'No medium priority tasks')}
        </div>
      </div>

      {/* Low Priority */}
      <div className="tasks-priority-card">
        <div className="priority-sec-title low">
          <span>🟢</span> Low Priority (<span id="task-count-low">{lowTasks.length}</span>)
        </div>
        <div className="tasks-table-list" id="tasks-list-low">
          {renderTaskCategory(lowTasks, 'No low priority tasks')}
        </div>
      </div>
    </section>
  );
}
