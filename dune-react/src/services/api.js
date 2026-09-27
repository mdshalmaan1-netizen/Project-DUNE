/**
 * DUNE Fullstack API Client
 * Communicates with the Node.js / Express backend (default: http://localhost:8000/api)
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('dune_auth_token') || '';
    this.isBackendOnline = false;
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem('dune_auth_token', token);
    } else {
      localStorage.removeItem('dune_auth_token');
    }
  }

  getHeaders(isFormData = false) {
    const headers = {};
    if (!isFormData) {
      headers['Content-Type'] = 'application/json';
    }
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = this.getHeaders(options.body instanceof FormData);

    try {
      const resp = await fetch(url, {
        ...options,
        headers: {
          ...headers,
          ...options.headers,
        },
      });

      if (!resp.ok) {
        const errorData = await resp.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error! status: ${resp.status}`);
      }

      this.isBackendOnline = true;
      return await resp.json();
    } catch (err) {
      // If network failure, mark backend offline
      if (err.name === 'TypeError' || err.message.includes('fetch failed') || err.message.includes('Failed to fetch')) {
        this.isBackendOnline = false;
      }
      throw err;
    }
  }

  // Health check
  async checkHealth() {
    try {
      const data = await this.request('/health', { method: 'GET' });
      this.isBackendOnline = true;
      return data;
    } catch (err) {
      this.isBackendOnline = false;
      return null;
    }
  }

  // Auth Endpoints
  async signup(userData) {
    const data = await this.request('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
    if (data.token) this.setToken(data.token);
    return data;
  }

  async login(email, password) {
    const data = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (data.token) this.setToken(data.token);
    return data;
  }

  async getProfile() {
    return this.request('/auth/me');
  }

  async updateProfile(profileData) {
    return this.request('/auth/profile', {
      method: 'PUT',
      body: JSON.stringify(profileData),
    });
  }

  // Tasks Endpoints
  async getTasks() {
    return this.request('/tasks');
  }

  async createTask(taskData) {
    return this.request('/tasks', {
      method: 'POST',
      body: JSON.stringify(taskData),
    });
  }

  async toggleTask(taskId) {
    return this.request(`/tasks/${taskId}/toggle`, {
      method: 'PATCH',
    });
  }

  async deleteTask(taskId) {
    return this.request(`/tasks/${taskId}`, {
      method: 'DELETE',
    });
  }

  // Schedule Endpoints
  async getSchedule() {
    return this.request('/schedule');
  }

  async createScheduleItem(scheduleData) {
    return this.request('/schedule', {
      method: 'POST',
      body: JSON.stringify(scheduleData),
    });
  }

  async updateScheduleItem(scheduleData) {
    return this.request('/schedule/update', {
      method: 'PUT',
      body: JSON.stringify(scheduleData),
    });
  }

  async deleteScheduleItem(scheduleId) {
    return this.request(`/schedule/${scheduleId}`, {
      method: 'DELETE',
    });
  }

  // Documents Endpoints
  async getDocuments() {
    return this.request('/documents');
  }

  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  }

  async deleteDocument(documentId) {
    return this.request(`/documents/${documentId}`, {
      method: 'DELETE',
    });
  }

  // Chat & AI Endpoints
  async sendChatMessage({ prompt, conversationId, history, apiKey }) {
    return this.request('/chat', {
      method: 'POST',
      body: JSON.stringify({ prompt, conversationId, history, apiKey }),
    });
  }

  async getConversations() {
    return this.request('/chat/conversations');
  }

  async deleteConversation(convId) {
    return this.request(`/chat/conversations/${convId}`, {
      method: 'DELETE',
    });
  }

  // Notifications Endpoints
  async getNotifications() {
    return this.request('/notifications');
  }

  async markNotificationRead(notifId) {
    return this.request(`/notifications/${notifId}/read`, {
      method: 'PATCH',
    });
  }
}

export const api = new ApiClient();
export default api;
