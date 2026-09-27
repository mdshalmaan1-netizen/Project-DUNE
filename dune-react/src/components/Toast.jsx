import React from 'react';
import { useStore } from '../store/useStore';

export default function Toast() {
  const { toast } = useStore();

  if (!toast.show) return null;

  return (
    <div id="toast-notification" style={{ display: 'flex' }}>
      <span id="toast-icon">{toast.icon || '🌸'}</span>
      <span id="toast-message">{toast.message}</span>
    </div>
  );
}
