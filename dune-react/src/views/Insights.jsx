import React from 'react';
import { useStore } from '../store/useStore';
import EmptyState from '../components/EmptyState';

export default function Insights() {
  const { state, openNewTaskModal } = useStore();

  const activeTasks = state.tasks.filter(t => !t.completed);
  const highPriorityTasks = activeTasks.filter(t => t.priority === 'high');

  return (
    <section id="view-insights" className="view-section active">
      <div className="dash-card" id="insights-container">
        {activeTasks.length === 0 ? (
          <EmptyState
            icon="📈"
            title="No Academic Bottlenecks Detected"
            desc="You have no overdue assignments or high-stress deadlines registered."
            actionLabel="+ Add Tasks to Track"
            onAction={openNewTaskModal}
          />
        ) : (
          <>
            <h3 style={{ fontSize: '18px', fontWeight: 800, marginBottom: '12px' }}>
              📊 Academic Workload Insights
            </h3>
            <p style={{ fontSize: '13.5px', color: 'var(--text-muted)', marginBottom: '20px' }}>
              You currently have <strong>{activeTasks.length} active tasks</strong>.{' '}
              {highPriorityTasks.length > 0
                ? 'High-priority items require immediate attention.'
                : 'Workload is evenly balanced.'}
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
              <div
                style={{
                  background: '#fdfafc',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '14px',
                  padding: '16px',
                  textAlign: 'center'
                }}
              >
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Active Tasks</div>
                <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)' }}>
                  {activeTasks.length}
                </div>
              </div>
              <div
                style={{
                  background: '#fdfafc',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '14px',
                  padding: '16px',
                  textAlign: 'center'
                }}
              >
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>High Priority</div>
                <div style={{ fontSize: '24px', fontWeight: 800, color: '#ef4444' }}>
                  {highPriorityTasks.length}
                </div>
              </div>
              <div
                style={{
                  background: '#fdfafc',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '14px',
                  padding: '16px',
                  textAlign: 'center'
                }}
              >
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Indexed Files</div>
                <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--primary)' }}>
                  {state.files.length}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
