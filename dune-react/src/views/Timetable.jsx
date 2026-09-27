import React from 'react';
import { useStore } from '../store/useStore';
import EmptyState from '../components/EmptyState';

export default function Timetable() {
  const { state, openAddScheduleModal, deleteScheduleItem } = useStore();

  return (
    <section id="view-timetable" className="view-section active">
      <div className="dash-card">
        <div className="card-header-flex">
          <div>
            <h3><span>🕒</span> Weekly Class Timetable</h3>
            <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Organize your weekly lectures and labs
            </p>
          </div>
          <button className="btn-action-primary" onClick={openAddScheduleModal}>
            <span>➕</span> Add Class Slot
          </button>
        </div>

        <div id="timetable-container">
          {state.schedule.length === 0 ? (
            <EmptyState
              icon="🗓️"
              title="No Timetable / Schedule Added Yet"
              desc="Add your weekly class periods and lecture times to build your timetable."
              actionLabel="+ Add First Class"
              onAction={openAddScheduleModal}
            />
          ) : (
            <table className="timetable-table">
              <thead>
                <tr>
                  <th>Day</th>
                  <th>Time</th>
                  <th>Course / Subject</th>
                  <th>Room</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {state.schedule.map(s => (
                  <tr key={s.id}>
                    <td><strong>{s.day}</strong></td>
                    <td>{s.time}</td>
                    <td><strong>{s.title}</strong></td>
                    <td>{s.room || '-'}</td>
                    <td>
                      <button
                        className="btn-del-task"
                        onClick={() => deleteScheduleItem(s.id)}
                        title="Delete Class Slot"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
}
