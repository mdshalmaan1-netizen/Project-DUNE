import React from 'react';
import { useStore } from '../store/useStore';
import EmptyState from '../components/EmptyState';

export default function Calendar() {
  const { state, openAddScheduleModal, deleteScheduleItem } = useStore();

  return (
    <section id="view-calendar" className="view-section active">
      <div className="calendar-card">
        <div className="cal-header-bar">
          <h3 id="calendar-month-title"><span>📅</span> Schedule & Calendar</h3>
          <button className="btn-action-primary" onClick={openAddScheduleModal}>
            <span>➕</span> Add Schedule Event
          </button>
        </div>

        <div id="calendar-events-container">
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
                        title="Delete Event"
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
