import React, { useState, useEffect } from 'react';
import { useStore } from '../../store/useStore';

export default function TaskModal() {
  const { isTaskModalOpen, closeTaskModal, addTask } = useStore();
  const [title, setTitle] = useState('');
  const [priority, setPriority] = useState('med');
  const [due, setDue] = useState('');

  useEffect(() => {
    if (isTaskModalOpen) {
      setTitle('');
      setPriority('med');
      setDue(new Date().toISOString().split('T')[0]);
    }
  }, [isTaskModalOpen]);

  if (!isTaskModalOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    addTask({ title, priority, due });
  };

  return (
    <div className="modal-overlay active" id="task-modal">
      <div className="modal-box">
        <button className="modal-close-btn" type="button" onClick={closeTaskModal}>✕</button>
        <h3 style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-main)', marginBottom: '16px' }}>
          <span>➕</span> Add New Academic Task
        </h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group" style={{ marginBottom: '14px' }}>
            <label>Task Title</label>
            <input
              type="text"
              id="new-task-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Complete Physics Assignment 2"
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: '14px' }}>
            <label>Priority</label>
            <select
              id="new-task-priority"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
            >
              <option value="high">High Priority 🔴</option>
              <option value="med">Medium Priority 🟡</option>
              <option value="low">Low Priority 🟢</option>
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: '20px' }}>
            <label>Due Date</label>
            <input
              type="date"
              id="new-task-due"
              value={due}
              onChange={(e) => setDue(e.target.value)}
              required
            />
          </div>
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="btn-show-actions"
              style={{ background: '#f1f5f9', color: 'var(--text-main)', boxShadow: 'none' }}
              onClick={closeTaskModal}
            >
              Cancel
            </button>
            <button type="submit" className="btn-action-primary">
              Create Task
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
