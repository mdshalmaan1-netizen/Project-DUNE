export function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function formatMarkdown(md) {
  if (!md) return '';
  let str = escapeHtml(md);
  str = str.replace(/^### (.*$)/gim, '<h3 style="margin:8px 0 4px;font-size:15px;color:var(--primary-dark);">$1</h3>');
  str = str.replace(/^## (.*$)/gim, '<h2 style="margin:10px 0 4px;font-size:16px;">$1</h2>');
  str = str.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  str = str.replace(/\*(.*?)\*/g, '<em>$1</em>');
  str = str.replace(/`(.*?)`/g, '<code style="background:#fff0f5;color:#ff4b82;padding:2px 6px;border-radius:4px;font-family:monospace;">$1</code>');
  str = str.replace(/\n\n+/g, '<br><br>');
  str = str.replace(/\n/g, '<br>');
  return str;
}
