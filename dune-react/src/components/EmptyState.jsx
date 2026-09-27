import React from 'react';

export default function EmptyState({ icon, title, desc, actionLabel, onAction, actionClassName = 'btn-action-primary', style }) {
  return (
    <div className="empty-state-container" style={style}>
      {icon && <div className="empty-state-icon">{icon}</div>}
      {title && <div className="empty-state-title">{title}</div>}
      {desc && <div className="empty-state-desc">{desc}</div>}
      {actionLabel && onAction && (
        <button className={actionClassName} onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}
