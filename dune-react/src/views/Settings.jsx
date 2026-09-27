import React, { useState, useEffect } from 'react';
import { useStore } from '../store/useStore';

export default function Settings() {
  const { state, saveProfileSettings, clearAllData } = useStore();

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    university: '',
    semester: '',
    major: '',
    apiKey: ''
  });

  useEffect(() => {
    if (state.user) {
      setFormData({
        name: state.user.name || '',
        email: state.user.email || '',
        university: state.user.university || '',
        semester: state.user.semester || '',
        major: state.user.major || '',
        apiKey: state.user.apiKey || ''
      });
    }
  }, [state.user]);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    saveProfileSettings({
      name: formData.name.trim(),
      email: formData.email.trim(),
      university: formData.university.trim(),
      semester: formData.semester.trim(),
      major: formData.major.trim(),
      apiKey: formData.apiKey.trim()
    });
  };

  return (
    <section id="view-settings" className="view-section active">
      <div className="settings-card">
        <h3 style={{ fontSize: '18px', fontWeight: 800, marginBottom: '6px' }}>
          Student Profile & AI Configuration
        </h3>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
          Configure your academic profile and Google Gemini AI keys.
        </p>

        <form id="profile-settings-form" onSubmit={handleSubmit}>
          <div className="profile-form-grid">
            <div className="form-group">
              <label>Full Name</label>
              <input
                type="text"
                id="setting-user-name"
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                placeholder="e.g. Alex Johnson"
                required
              />
            </div>
            <div className="form-group">
              <label>Student Email</label>
              <input
                type="email"
                id="setting-user-email"
                value={formData.email}
                onChange={(e) => handleChange('email', e.target.value)}
                placeholder="e.g. student@university.edu"
              />
            </div>
            <div className="form-group">
              <label>University / College</label>
              <input
                type="text"
                id="setting-user-uni"
                value={formData.university}
                onChange={(e) => handleChange('university', e.target.value)}
                placeholder="e.g. Stanford University"
              />
            </div>
            <div className="form-group">
              <label>Current Semester / Year</label>
              <input
                type="text"
                id="setting-user-sem"
                value={formData.semester}
                onChange={(e) => handleChange('semester', e.target.value)}
                placeholder="e.g. Semester 6 / Year 3"
              />
            </div>
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label>Major / Field of Study</label>
              <input
                type="text"
                id="setting-user-major"
                value={formData.major}
                onChange={(e) => handleChange('major', e.target.value)}
                placeholder="e.g. Computer Science & Engineering"
              />
            </div>
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label>Google Gemini API Key (Optional / Custom)</label>
              <input
                type="password"
                id="setting-gemini-key"
                value={formData.apiKey}
                onChange={(e) => handleChange('apiKey', e.target.value)}
                placeholder="Enter your Google Gemini API Key for direct cloud generation"
              />
              <small style={{ color: 'var(--text-muted)', fontSize: '11px', marginTop: '3px' }}>
                Leave blank to use DUNE's built-in intelligent precision reasoning engine.
              </small>
            </div>
          </div>

          <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
            <button type="submit" className="btn-action-primary">
              Save Settings
            </button>
            <button
              type="button"
              className="btn-show-actions"
              style={{ background: '#fee2e2', color: '#ef4444', boxShadow: 'none' }}
              onClick={clearAllData}
            >
              Clear All Data
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
