import React from 'react';
import { useStore } from '../store/useStore';
import EmptyState from '../components/EmptyState';

export default function RiskAlerts() {
  const { state, sendQuickChat } = useStore();

  const urgentTasks = state.tasks.filter(t => !t.completed && t.priority === 'high');

  return (
    <section id="view-risk" className="view-section active">
      <div className="tasks-header-bar">
        <h2>Academic Early Warning System</h2>
      </div>

      <div className="risk-cards-list" id="risk-alerts-container">
        {urgentTasks.length === 0 ? (
          <EmptyState
            icon="🛡️"
            title="All Systems Clear"
            desc="No urgent high-risk deadlines or conflicts detected right now."
          />
        ) : (
          urgentTasks.map(t => (
            <div
              key={t.id}
              className="task-interactive-row"
              style={{ borderLeft: '5px solid #ef4444' }}
            >
              <div>
                <h4 style={{ fontSize: '14.5px', fontWeight: 700, color: '#be123c' }}>
                  🔴 {t.title}
                </h4>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Due: {t.due} • High Priority
                </p>
              </div>
              <button
                className="btn-action-primary"
                style={{ padding: '6px 14px', fontSize: '12px' }}
                onClick={() => sendQuickChat(`Help me solve and prepare for: ${t.title}`)}
              >
                Solve with DUNE
              </button>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
