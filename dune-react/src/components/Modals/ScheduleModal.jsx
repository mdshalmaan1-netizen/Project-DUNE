import React, { useState, useEffect } from 'react';
import { useStore } from '../../store/useStore';

export default function ScheduleModal() {
  const { isScheduleModalOpen, closeScheduleModal, addScheduleItem } = useStore();
  const [title, setTitle] = useState('');
  const [day, setDay] = useState('Mon');
  const [time, setTime] = useState('09:00');
  const [room, setRoom] = useState('');

  useEffect(() => {
    if (isScheduleModalOpen) {
      setTitle('');
      setDay('Mon');
      setTime('09:00');
      setRoom('');
    }
  }, [isScheduleModalOpen]);

  if (!isScheduleModalOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    addScheduleItem({ title, day, time, room });
  };

  return (
    <div className="modal-overlay active" id="schedule-modal">
      <div className="modal-box">
        <button className="modal-close-btn" type="button" onClick={closeScheduleModal}>✕</button>
        <h3 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-main)', marginBottom: '16px' }}>
          <span>📅</span> Add Class / Schedule Event
        </h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group" style={{ marginBottom: '14px' }}>
            <label>Course / Event Title</label>
            <input
              type="text"
              id="new-sched-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Operating Systems Lecture"
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: '14px' }}>
            <label>Day of Week</label>
            <select
              id="new-sched-day"
              value={day}
              onChange={(e) => setDay(e.target.value)}
            >
              <option value="Mon">Monday</option>
              <option value="Tue">Tuesday</option>
              <option value="Wed">Wednesday</option>
              <option value="Thu">Thursday</option>
              <option value="Fri">Friday</option>
              <option value="Sat">Saturday</option>
              <option value="Sun">Sunday</option>
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: '14px' }}>
            <label>Time</label>
            <input
              type="time"
              id="new-sched-time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: '20px' }}>
            <label>Location / Room</label>
            <input
              type="text"
              id="new-sched-room"
              value={room}
              onChange={(e) => setRoom(e.target.value)}
              placeholder="e.g. Hall B / Online"
            />
          </div>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="btn-show-actions"
              style={{ background: '#f1f5f9', color: 'var(--text-main)', boxShadow: 'none' }}
              onClick={closeScheduleModal}
            >
              Cancel
            </button>
            <button type="submit" className="btn-action-primary">
              Save to Schedule
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
