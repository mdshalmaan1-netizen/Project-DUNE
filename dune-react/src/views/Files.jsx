import React from 'react';
import { useStore } from '../store/useStore';
import EmptyState from '../components/EmptyState';

export default function Files() {
  const { state, deleteFile, askAboutFile } = useStore();

  const triggerUpload = () => {
    const input = document.getElementById('doc-file-input');
    if (input) input.click();
  };

  return (
    <section id="view-files" className="view-section active">
      <div className="files-table-card">
        <div className="table-toolbar">
          <div>
            <h3>Academic Documents & Notes</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Upload your syllabus, lecture slides, or assignments to let DUNE index them.
            </p>
          </div>
          <button className="btn-action-primary" onClick={triggerUpload}>
            <span>➕</span> Upload Document (PDF/Text)
          </button>
        </div>

        <div id="files-list-container">
          {state.files.length === 0 ? (
            <EmptyState
              icon="📁"
              title="No Documents Uploaded"
              desc="Upload your PDF notes, syllabus, or lecture slides to enable deep AI assistance."
              actionLabel="➕ Upload Document"
              onAction={triggerUpload}
              style={{ margin: '24px' }}
            />
          ) : (
            <table className="files-table">
              <thead>
                <tr>
                  <th>File Name</th>
                  <th>Type</th>
                  <th>Uploaded Date</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {state.files.map(f => (
                  <tr key={f.id}>
                    <td><strong>📄 {f.name}</strong></td>
                    <td><span className="badge-pill">{f.type || 'PDF'}</span></td>
                    <td>{f.date}</td>
                    <td>
                      <button
                        className="btn-show-actions"
                        style={{ padding: '4px 10px', fontSize: '11px' }}
                        onClick={() => askAboutFile(f.name)}
                      >
                        Ask DUNE
                      </button>
                      <button
                        className="btn-del-task"
                        style={{ marginLeft: '8px' }}
                        onClick={() => deleteFile(f.id)}
                        title="Delete Document"
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
