import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { generateAccurateResponse } from '../services/aiEngine';
import api from '../services/api';

const STORAGE_KEY = 'dune_student_state_v2';

const defaultState = {
  user: {
    name: '',
    email: '',
    university: '',
    semester: '',
    major: '',
    apiKey: ''
  },
  tasks: [],
  schedule: [],
  files: [],
  conversations: [],
  activeConversationId: '',
  chatHistory: []
};

const DuneContext = createContext(null);

export function DuneProvider({ children }) {
  const [state, setState] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        const merged = { ...defaultState, ...parsed };

        // Ensure conversations array exists
        if (!merged.conversations || !Array.isArray(merged.conversations) || merged.conversations.length === 0) {
          if (merged.chatHistory && merged.chatHistory.length > 0) {
            const firstUserMsg = merged.chatHistory.find(m => m.role === 'user');
            const title = firstUserMsg ? firstUserMsg.text.slice(0, 30) + '...' : 'Previous Conversation';
            const initConv = {
              id: 'conv_' + Date.now(),
              title: title,
              createdAt: new Date().toLocaleDateString(),
              messages: merged.chatHistory
            };
            merged.conversations = [initConv];
            merged.activeConversationId = initConv.id;
          } else {
            const initConv = {
              id: 'conv_' + Date.now(),
              title: 'New Conversation',
              createdAt: new Date().toLocaleDateString(),
              messages: []
            };
            merged.conversations = [initConv];
            merged.activeConversationId = initConv.id;
            merged.chatHistory = [];
          }
        } else if (!merged.activeConversationId) {
          merged.activeConversationId = merged.conversations[0].id;
          merged.chatHistory = merged.conversations[0].messages || [];
        } else {
          const active = merged.conversations.find(c => c.id === merged.activeConversationId) || merged.conversations[0];
          merged.chatHistory = active ? (active.messages || []) : [];
        }

        return merged;
      }
    } catch (e) {
      console.error("State parse error", e);
    }

    const initialConvId = 'conv_' + Date.now();
    return {
      ...defaultState,
      conversations: [
        {
          id: initialConvId,
          title: 'New Conversation',
          createdAt: new Date().toLocaleDateString(),
          messages: []
        }
      ],
      activeConversationId: initialConvId,
      chatHistory: []
    };
  });

  const [activeView, setActiveView] = useState('dashboard');
  const [isTaskModalOpen, setIsTaskModalOpen] = useState(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [toast, setToast] = useState({ show: false, message: '', icon: '🌸' });
  const [isAiTyping, setIsAiTyping] = useState(false);

  const toastTimerRef = useRef(null);

  // Sync state to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      console.error("Failed to save state to localStorage", e);
    }
  }, [state]);

  // Initial sync with Node.js Express Backend
  useEffect(() => {
    async function syncBackendData() {
      const health = await api.checkHealth();
      if (!health) return;

      try {
        const [backendTasks, backendSchedule, backendDocs] = await Promise.all([
          api.getTasks().catch(() => null),
          api.getSchedule().catch(() => null),
          api.getDocuments().catch(() => null)
        ]);

        setState(prev => {
          const next = { ...prev };
          if (Array.isArray(backendTasks) && backendTasks.length > 0) {
            const taskIds = new Set(backendTasks.map(t => t.id || t._id));
            const localUnique = prev.tasks.filter(t => !taskIds.has(t.id));
            next.tasks = [...backendTasks.map(t => ({
              id: t.id || t._id,
              title: t.title,
              priority: t.priority,
              due: t.due,
              completed: !!t.completed
            })), ...localUnique];
          }

          if (Array.isArray(backendSchedule) && backendSchedule.length > 0) {
            const schedIds = new Set(backendSchedule.map(s => s.id || s._id));
            const localUnique = prev.schedule.filter(s => !schedIds.has(s.id));
            next.schedule = [...backendSchedule.map(s => ({
              id: s.id || s._id,
              title: s.title,
              day: s.day,
              time: s.time,
              room: s.room
            })), ...localUnique];
          }

          if (Array.isArray(backendDocs) && backendDocs.length > 0) {
            const docIds = new Set(backendDocs.map(d => d.id || d._id));
            const localUnique = prev.files.filter(f => !docIds.has(f.id));
            next.files = [...backendDocs.map(d => ({
              id: d.id || d._id,
              name: d.name,
              type: d.type || 'PDF',
              date: d.date,
              content: d.content || '',
              chunkCount: d.chunkCount || 0
            })), ...localUnique];
          }

          return next;
        });
      } catch (err) {
        console.warn("Backend sync notice:", err.message);
      }
    }

    syncBackendData();
  }, []);

  const showToast = (message, icon = '🌸') => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ show: true, message, icon });
    toastTimerRef.current = setTimeout(() => {
      setToast({ show: false, message: '', icon: '🌸' });
    }, 3500);
  };

  const switchView = (viewName) => {
    setActiveView(viewName);
  };

  const openNewTaskModal = () => setIsTaskModalOpen(true);
  const closeTaskModal = () => setIsTaskModalOpen(false);

  const openAddScheduleModal = () => setIsScheduleModalOpen(true);
  const closeScheduleModal = () => setIsScheduleModalOpen(false);

  // ChatGPT-Style Conversation Management
  const createNewChat = () => {
    const newId = 'conv_' + Date.now();
    const newConv = {
      id: newId,
      title: 'New Conversation',
      createdAt: new Date().toLocaleDateString(),
      messages: []
    };
    setState(prev => ({
      ...prev,
      conversations: [newConv, ...(prev.conversations || [])],
      activeConversationId: newId,
      chatHistory: []
    }));
    showToast('Started new chat!', '✨');
  };

  const selectConversation = (id) => {
    setState(prev => {
      const conv = (prev.conversations || []).find(c => c.id === id);
      return {
        ...prev,
        activeConversationId: id,
        chatHistory: conv ? (conv.messages || []) : []
      };
    });
  };

  const deleteConversation = (id, e) => {
    if (e) e.stopPropagation();
    setState(prev => {
      const remaining = (prev.conversations || []).filter(c => c.id !== id);
      if (remaining.length === 0) {
        const freshId = 'conv_' + Date.now();
        const freshConv = {
          id: freshId,
          title: 'New Conversation',
          createdAt: new Date().toLocaleDateString(),
          messages: []
        };
        return {
          ...prev,
          conversations: [freshConv],
          activeConversationId: freshId,
          chatHistory: []
        };
      }
      const nextActiveId = prev.activeConversationId === id ? remaining[0].id : prev.activeConversationId;
      const nextActiveConv = remaining.find(c => c.id === nextActiveId);
      return {
        ...prev,
        conversations: remaining,
        activeConversationId: nextActiveId,
        chatHistory: nextActiveConv ? (nextActiveConv.messages || []) : []
      };
    });
    showToast('Chat removed', '🗑️');
  };

  const addTask = async ({ title, priority, due }) => {
    if (!title) return;
    const newTask = {
      id: 'task_' + Date.now(),
      title: title.trim(),
      priority: priority || 'med',
      due: due || new Date().toISOString().split('T')[0],
      completed: false
    };
    setState(prev => ({
      ...prev,
      tasks: [newTask, ...prev.tasks]
    }));
    closeTaskModal();
    showToast('Task added successfully!', '✅');

    // Sync to Express Backend
    try {
      const serverTask = await api.createTask({
        title: newTask.title,
        priority: newTask.priority,
        due: newTask.due
      });
      if (serverTask && (serverTask.id || serverTask._id)) {
        setState(prev => ({
          ...prev,
          tasks: prev.tasks.map(t => t.id === newTask.id ? { ...t, id: serverTask.id || serverTask._id } : t)
        }));
      }
    } catch (e) {
      // offline fallback retained
    }
  };

  const toggleTaskStatus = (id) => {
    let completedStatus = false;
    setState(prev => {
      const newTasks = prev.tasks.map(t => {
        if (t.id === id) {
          completedStatus = !t.completed;
          return { ...t, completed: !t.completed };
        }
        return t;
      });
      return { ...prev, tasks: newTasks };
    });
    showToast(completedStatus ? 'Task completed!' : 'Task marked pending', '🎉');
    api.toggleTask(id).catch(() => {});
  };

  const deleteTask = (id) => {
    setState(prev => ({
      ...prev,
      tasks: prev.tasks.filter(t => t.id !== id)
    }));
    showToast('Task removed', '🗑️');
    api.deleteTask(id).catch(() => {});
  };

  const addScheduleItem = async ({ title, day, time, room }) => {
    if (!title) return;
    const newSched = {
      id: 'sched_' + Date.now(),
      title: title.trim(),
      day: day || 'Mon',
      time: time || '09:00',
      room: room ? room.trim() : ''
    };
    setState(prev => ({
      ...prev,
      schedule: [...prev.schedule, newSched]
    }));
    closeScheduleModal();
    showToast('Class added to schedule!', '📅');

    // Sync to Express Backend
    try {
      const serverSched = await api.createScheduleItem({
        title: newSched.title,
        day: newSched.day,
        time: newSched.time,
        room: newSched.room
      });
      if (serverSched && (serverSched.id || serverSched._id)) {
        setState(prev => ({
          ...prev,
          schedule: prev.schedule.map(s => s.id === newSched.id ? { ...s, id: serverSched.id || serverSched._id } : s)
        }));
      }
    } catch (e) {
      // offline fallback retained
    }
  };

  const deleteScheduleItem = (id) => {
    setState(prev => ({
      ...prev,
      schedule: prev.schedule.filter(s => s.id !== id)
    }));
    showToast('Schedule event removed', '🗑️');
    api.deleteScheduleItem(id).catch(() => {});
  };

  const updateScheduleItem = ({ id, day, time, title, room }) => {
    const dayMap = {
      monday: 'Mon', mon: 'Mon', thingal: 'Mon',
      tuesday: 'Tue', tue: 'Tue', sevvaai: 'Tue',
      wednesday: 'Wed', wed: 'Wed', budhan: 'Wed',
      thursday: 'Thu', thu: 'Thu', viyazhan: 'Thu',
      friday: 'Fri', fri: 'Fri', velli: 'Fri',
      saturday: 'Sat', sat: 'Sat', sani: 'Sat',
      sunday: 'Sun', sun: 'Sun', nyaayiru: 'Sun'
    };
    const dayKey = (day || '').toLowerCase();
    const formattedDay = dayMap[dayKey] || (day ? day.charAt(0).toUpperCase() + day.slice(1, 3).toLowerCase() : 'Mon');

    let resolvedTarget = {
      id: id || '',
      day: formattedDay,
      time: time || '10:00',
      title: title || 'New Class',
      room: room || ''
    };

    setState(prev => {
      let matched = false;
      const nextSched = prev.schedule.map(s => {
        const idMatch = id && (s.id === id || s._id === id);
        const dayMatch = day ? (s.day || '').toLowerCase().startsWith(formattedDay.toLowerCase()) : true;
        const timeMatch = time ? s.time.replace(/\s+/g, '').includes(time.replace(/\s+/g, '')) : true;

        if (!matched && (idMatch || (dayMatch && timeMatch))) {
          matched = true;
          resolvedTarget = {
            ...s,
            title: title || s.title,
            day: formattedDay || s.day,
            time: time || s.time,
            room: room !== undefined ? room : (s.room || '')
          };
          return resolvedTarget;
        }
        return s;
      });

      // If day/time exact match wasn't found, try matching by day alone
      if (!matched) {
        for (let i = 0; i < nextSched.length; i++) {
          const s = nextSched[i];
          const sDay = (s.day || '').toLowerCase();
          if (sDay.startsWith(formattedDay.toLowerCase())) {
            matched = true;
            resolvedTarget = {
              ...s,
              title: title || s.title,
              day: formattedDay || s.day,
              time: time || s.time,
              room: room !== undefined ? room : (s.room || '')
            };
            nextSched[i] = resolvedTarget;
            break;
          }
        }
      }

      if (!matched && title) {
        resolvedTarget = {
          id: 'sched_' + Date.now(),
          title: title.trim(),
          day: formattedDay,
          time: time || '10:00',
          room: room || 'Hall B - 204'
        };
        nextSched.push(resolvedTarget);
      }

      return { ...prev, schedule: nextSched };
    });

    showToast(`Timetable updated: ${resolvedTarget.day} ${resolvedTarget.time} ➔ ${resolvedTarget.title}!`, '🕒');
    api.updateScheduleItem(resolvedTarget).catch(e => console.warn("Backend schedule update error:", e));
    return resolvedTarget;
  };

  const executeAppAction = (action) => {
    if (!action || !action.type) return null;

    switch (action.type) {
      case 'UPDATE_SCHEDULE': {
        const { day, time, title, room, newTitle } = action;
        const targetTitle = newTitle || title;
        if (!targetTitle) return null;
        const res = updateScheduleItem({ day, time, title: targetTitle, room });
        return `Updated Timetable: ${res?.day || (day || 'Mon')} ${res?.time || (time || '10:00')} ➔ ${targetTitle}`;
      }

      case 'ADD_SCHEDULE': {
        const { title, day, time, room } = action;
        if (title) {
          addScheduleItem({ title, day, time, room });
          return `Added to Timetable: ${title}`;
        }
        return null;
      }

      case 'DELETE_SCHEDULE': {
        const { title, day, time, id } = action;
        let deleted = false;
        setState(prev => {
          const filtered = prev.schedule.filter(s => {
            if (id && (s.id === id || s._id === id)) return false;
            const titleMatch = title ? s.title.toLowerCase().includes(title.toLowerCase()) : false;
            const dayMatch = day ? (s.day || '').toLowerCase().startsWith(day.toLowerCase().slice(0, 3)) : false;
            if ((titleMatch || (dayMatch && time && s.time.includes(time))) && !deleted) {
              deleted = true;
              api.deleteScheduleItem(s.id).catch(() => {});
              return false;
            }
            return true;
          });
          return { ...prev, schedule: filtered };
        });
        showToast('Timetable slot removed', '🗑️');
        return `Removed from Timetable`;
      }

      case 'ADD_TASK': {
        const { title, priority, due } = action;
        if (title) {
          addTask({ title, priority, due });
          return `Created task: ${title}`;
        }
        return null;
      }

      case 'COMPLETE_TASK': {
        const { title, id } = action;
        let toggled = false;
        setState(prev => {
          const updated = prev.tasks.map(t => {
            const isMatch = (id && (t.id === id || t._id === id)) || 
                            (title && t.title.toLowerCase().includes(title.toLowerCase()));
            if (isMatch && !toggled) {
              toggled = true;
              api.toggleTask(t.id).catch(() => {});
              return { ...t, completed: true };
            }
            return t;
          });
          return { ...prev, tasks: updated };
        });
        if (toggled) showToast('Task marked completed!', '🎉');
        return `Task marked completed`;
      }

      case 'DELETE_TASK': {
        const { title, id } = action;
        let removed = false;
        setState(prev => {
          const filtered = prev.tasks.filter(t => {
            const isMatch = (id && (t.id === id || t._id === id)) || 
                            (title && t.title.toLowerCase().includes(title.toLowerCase()));
            if (isMatch && !removed) {
              removed = true;
              api.deleteTask(t.id).catch(() => {});
              return false;
            }
            return true;
          });
          return { ...prev, tasks: filtered };
        });
        if (removed) showToast('Task removed', '🗑️');
        return `Task removed`;
      }

      case 'UPDATE_PROFILE': {
        const { field, value, name, semester, university, major } = action;
        const updates = {};
        if (field && value) updates[field] = value;
        if (name) updates.name = name;
        if (semester) updates.semester = semester;
        if (university) updates.university = university;
        if (major) updates.major = major;
        saveProfileSettings(updates);
        return `Profile updated`;
      }

      case 'NAVIGATE_VIEW': {
        if (action.view) {
          switchView(action.view);
          return `Navigated to ${action.view}`;
        }
        return null;
      }

      default:
        return null;
    }
  };

  const parseAndExecutePromptIntent = (prompt) => {
    if (!prompt) return null;
    const p = prompt.toLowerCase();
    const isSched = p.includes('time table') || p.includes('timetable') || p.includes('schedule') || p.includes('class') || p.includes('slot');
    const isChange = p.includes('maathu') || p.includes('change') || p.includes('update') || p.includes('replace') || p.includes('add') || p.includes('pannu') || p.includes('potuko');

    if (isSched && isChange) {
      const dayMap = {
        monday: 'Mon', mon: 'Mon', thingal: 'Mon',
        tuesday: 'Tue', tue: 'Tue', sevvaai: 'Tue',
        wednesday: 'Wed', wed: 'Wed', budhan: 'Wed',
        thursday: 'Thu', thu: 'Thu', viyazhan: 'Thu',
        friday: 'Fri', fri: 'Fri', velli: 'Fri',
        saturday: 'Sat', sat: 'Sat', sani: 'Sat',
        sunday: 'Sun', sun: 'Sun', nyaayiru: 'Sun'
      };
      let matchedDay = 'Mon';
      for (const [k, v] of Object.entries(dayMap)) {
        if (new RegExp('\\b' + k + '\\b', 'i').test(p)) {
          matchedDay = v;
          break;
        }
      }

      let timeStr = '10:00';
      const timeMatch = p.match(/(\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?)/i);
      if (timeMatch) {
        let t = timeMatch[1].toLowerCase().replace(/\s+/g, '').replace('.', ':');
        if (t.includes('am') || t.includes('pm')) {
          const isPm = t.includes('pm');
          const num = t.replace(/(am|pm)/, '');
          let [h, m] = num.includes(':') ? num.split(':') : [num, '00'];
          let hour = parseInt(h);
          if (isPm && hour < 12) hour += 12;
          if (!isPm && hour === 12) hour = 0;
          timeStr = String(hour).padStart(2, '0') + ':' + (m || '00');
        } else if (t.includes(':')) {
          let [h, m] = t.split(':');
          timeStr = String(parseInt(h)).padStart(2, '0') + ':' + m;
        } else {
          timeStr = String(parseInt(t)).padStart(2, '0') + ':00';
        }
      }

      let newTitle = null;
      const m1 = prompt.match(/(?:ah|to|into|va)\s+([A-Za-z0-9\s&+-]+?)(?:\s+nu|\s+class|\s+subject|$)/i);
      if (m1 && m1[1] && m1[1].trim().length > 1) {
        newTitle = m1[1].trim();
      } else {
        const m2 = prompt.match(/([A-Za-z0-9\s&+-]+?)\s+nu\s+(?:maathu|change|add|potuko|update)/i);
        if (m2 && m2[1]) newTitle = m2[1].trim();
      }

      if (newTitle) {
        return executeAppAction({
          type: 'UPDATE_SCHEDULE',
          day: matchedDay,
          time: timeStr,
          title: newTitle
        });
      }
    }

    // Task addition intent fallback
    const isTaskIntent = p.startsWith('add task') || p.startsWith('new task') || p.includes('task add pannu');
    if (isTaskIntent) {
      const taskTitle = prompt.replace(/^(add task|new task|task add pannu)[:\s]*/i, '').trim();
      if (taskTitle) {
        return executeAppAction({
          type: 'ADD_TASK',
          title: taskTitle,
          due: new Date().toISOString().split('T')[0],
          priority: 'med'
        });
      }
    }

    return null;
  };

  const deleteFile = (id) => {
    setState(prev => ({
      ...prev,
      files: prev.files.filter(f => f.id !== id)
    }));
    showToast('Document removed', '🗑️');
    api.deleteDocument(id).catch(() => {});
  };

  const handleFileUpload = async (file) => {
    if (!file) return;

    let extractedText = '';
    const isDocx = file.name.endsWith('.docx') || file.name.endsWith('.doc');
    const isPdf = file.name.endsWith('.pdf');

    if (isPdf) {
      try {
        const arrayBuffer = await file.arrayBuffer();
        if (window.pdfjsLib) {
          const pdf = await window.pdfjsLib.getDocument({ data: arrayBuffer }).promise;
          const maxPages = Math.min(pdf.numPages, 30);
          for (let i = 1; i <= maxPages; i++) {
            const page = await pdf.getPage(i);
            const content = await page.getTextContent();
            let lastY;
            let pageLines = [];
            let currentLine = '';
            for (const item of content.items) {
              if (lastY !== undefined && Math.abs(item.transform[5] - lastY) > 5) {
                if (currentLine.trim()) pageLines.push(currentLine.trim());
                currentLine = '';
              }
              currentLine += (item.str || '') + ' ';
              lastY = item.transform[5];
            }
            if (currentLine.trim()) pageLines.push(currentLine.trim());
            extractedText += `\n--- PAGE ${i} ---\n` + pageLines.join('\n') + '\n';
          }
        }
      } catch (err) {
        console.warn("PDF extraction issue", err);
      }
    } else if (isDocx) {
      try {
        if (window.mammoth) {
          const arrayBuffer = await file.arrayBuffer();
          const result = await window.mammoth.extractRawText({ arrayBuffer });
          extractedText = result.value || '';
        }
      } catch (err) {
        console.warn("DOCX extraction issue", err);
      }
    } else {
      try {
        extractedText = await file.text();
      } catch (err) {
        console.warn("Text extraction issue", err);
      }
    }

    let dataUrl = '';
    try {
      if (file.size < 16 * 1024 * 1024) {
        dataUrl = await new Promise((resolve) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = () => resolve('');
          reader.readAsDataURL(file);
        });
      }
    } catch (err) {
      console.warn("Could not read dataUrl", err);
    }

    const newFile = {
      id: 'file_' + Date.now(),
      name: file.name,
      type: file.name.split('.').pop().toUpperCase(),
      date: new Date().toLocaleDateString(),
      content: (extractedText || '').slice(0, 80000),
      dataUrl: dataUrl
    };

    const nextFiles = [newFile, ...state.files];
    setState(prev => ({
      ...prev,
      files: [newFile, ...prev.files]
    }));

    // Sync upload to Express Backend for full text RAG indexing
    api.uploadDocument(file).then(backendDoc => {
      if (backendDoc && (backendDoc.id || backendDoc._id)) {
        setState(prev => ({
          ...prev,
          files: prev.files.map(f => f.id === newFile.id ? { ...f, id: backendDoc.id || backendDoc._id } : f)
        }));
      }
    }).catch(err => console.warn("Backend upload notice:", err.message));

    showToast(`Uploaded and indexed "${file.name}"!`, '📄');
    switchView('chat');

    const isResume = /(resume|cv|biodata|profile|curriculum)/i.test(file.name) ||
                     /(education|experience|college|university|b\.tech|b\.e|skills|projects)/i.test((extractedText || '').slice(0, 2500));

    const initialPrompt = isResume
      ? `I uploaded my resume/document "${file.name}". Please analyze it thoroughly:
1. Candidate Name & Contact Details
2. College / University & Degree Details (where they are studying)
3. Key Technical & Domain Skills
4. Work Experience & Major Projects
Give a clear, structured summary in Tanglish & English, and let me know what questions I can ask you about this profile.`
      : `I uploaded "${file.name}". Please analyze this document and provide a structured summary of key concepts, formulas, definitions, and likely exam or interview questions.`;

    sendQuickChat(initialPrompt, { ...state, files: nextFiles });
  };

  const downloadFile = (fileObj) => {
    if (!fileObj) return;
    if (fileObj.dataUrl) {
      const a = document.createElement('a');
      a.href = fileObj.dataUrl;
      a.download = fileObj.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      showToast(`Downloading ${fileObj.name}...`, '📥');
    } else if (fileObj.content) {
      const blob = new Blob([fileObj.content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const downloadName = fileObj.name.endsWith('.pdf') ? fileObj.name.replace(/\.pdf$/i, '_extracted.txt') : fileObj.name;
      a.download = downloadName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast(`Downloading ${downloadName}...`, '📥');
    }
  };

  const downloadTextAsFile = (filename, contentText) => {
    if (!contentText) return;
    const blob = new Blob([contentText], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'DUNE_Notes.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Downloaded ${filename || 'DUNE_Notes.txt'}!`, '📥');
  };

  const askAboutFile = (fileName) => {
    switchView('chat');
    const isResume = /(resume|cv|biodata|profile)/i.test(fileName);
    if (isResume) {
      sendQuickChat(`What college, degree, skills, and experience are listed in "${fileName}"?`);
    } else {
      sendQuickChat(`What are the key concepts and exam topics in "${fileName}"?`);
    }
  };

  const saveProfileSettings = (userProfile) => {
    setState(prev => ({
      ...prev,
      user: { ...prev.user, ...userProfile }
    }));
    showToast('Settings & API key saved!', '👤');
    switchView('dashboard');
  };

  const updateApiKey = (apiKey) => {
    setState(prev => ({
      ...prev,
      user: { ...prev.user, apiKey: (apiKey || '').trim() }
    }));
    showToast('Gemini API key updated!', '⚡');
  };

  const clearAllData = () => {
    if (window.confirm('Are you sure you want to reset all tasks, schedule, chats, and uploaded files?')) {
      localStorage.removeItem(STORAGE_KEY);
      const freshId = 'conv_' + Date.now();
      setState({
        ...defaultState,
        conversations: [
          {
            id: freshId,
            title: 'New Conversation',
            createdAt: new Date().toLocaleDateString(),
            messages: []
          }
        ],
        activeConversationId: freshId,
        chatHistory: []
      });
      showToast('All data cleared.', '🗑️');
    }
  };

  const sendChatMessage = async (text, customState = null) => {
    const promptText = (text || '').trim();
    if (!promptText) return;

    const currentState = customState || state;
    const userMsg = { role: 'user', text: promptText };

    let activeId = currentState.activeConversationId;
    let conversations = [...(currentState.conversations || [])];
    let activeConvIndex = conversations.findIndex(c => c.id === activeId);

    if (activeConvIndex === -1) {
      const newId = 'conv_' + Date.now();
      const newConv = {
        id: newId,
        title: promptText.slice(0, 32) + (promptText.length > 32 ? '...' : ''),
        createdAt: new Date().toLocaleDateString(),
        messages: [userMsg]
      };
      conversations = [newConv, ...conversations];
      activeId = newId;
    } else {
      const activeConv = conversations[activeConvIndex];
      const shouldUpdateTitle = (activeConv.messages || []).length === 0 || activeConv.title === 'New Conversation';
      conversations[activeConvIndex] = {
        ...activeConv,
        title: shouldUpdateTitle ? promptText.slice(0, 32) + (promptText.length > 32 ? '...' : '') : activeConv.title,
        messages: [...(activeConv.messages || []), userMsg]
      };
    }

    const nextChatHistory = conversations.find(c => c.id === activeId)?.messages || [userMsg];

    setState(prev => ({
      ...prev,
      conversations: conversations,
      activeConversationId: activeId,
      chatHistory: nextChatHistory
    }));

    setIsAiTyping(true);

    try {
      const response = await generateAccurateResponse(promptText, {
        ...currentState,
        chatHistory: nextChatHistory
      });

      setIsAiTyping(false);

      // Parse and execute any live application actions
      let cleanText = response.text || '';
      let executedActionLabel = null;

      // 1. Check for machine action tag [ACTION:{...}]
      const actionMatch = cleanText.match(/\[ACTION:\s*(\{.*?\})\s*\]/is);
      if (actionMatch) {
        try {
          const actionObj = JSON.parse(actionMatch[1]);
          executedActionLabel = executeAppAction(actionObj);
          cleanText = cleanText.replace(actionMatch[0], '').trim();
        } catch (e) {
          console.warn("Could not parse AI action JSON:", e);
        }
      }

      // 2. Client-side smart intent fallback if user asked to update timetable/tasks and model didn't append tag
      if (!executedActionLabel) {
        executedActionLabel = parseAndExecutePromptIntent(promptText);
      }

      const aiMsg = { 
        role: 'ai', 
        text: cleanText, 
        citation: response.citation,
        actionExecuted: executedActionLabel 
      };

      setState(prev => {
        const updatedConversations = (prev.conversations || []).map(c => {
          if (c.id === activeId) {
            return { ...c, messages: [...(c.messages || []), aiMsg] };
          }
          return c;
        });
        const updatedActive = updatedConversations.find(c => c.id === activeId);
        return {
          ...prev,
          conversations: updatedConversations,
          chatHistory: updatedActive ? (updatedActive.messages || []) : []
        };
      });
    } catch (e) {
      console.error("AI Error:", e);
      setIsAiTyping(false);
      const errorMsg = { role: 'ai', text: `⚠️ Error: ${e.message}`, citation: 'System Error' };
      setState(prev => {
        const updatedConversations = (prev.conversations || []).map(c => {
          if (c.id === activeId) {
            return { ...c, messages: [...(c.messages || []), errorMsg] };
          }
          return c;
        });
        const updatedActive = updatedConversations.find(c => c.id === activeId);
        return {
          ...prev,
          conversations: updatedConversations,
          chatHistory: updatedActive ? (updatedActive.messages || []) : []
        };
      });
    }
  };

  const sendQuickChat = (promptText, customState = null) => {
    switchView('chat');
    sendChatMessage(promptText, customState);
  };

  const handleDashboardActionClick = () => {
    const activeTasks = state.tasks.filter(t => !t.completed);
    if (activeTasks.length > 0) {
      showToast(`Starting focus session for: ${activeTasks[0].title}`, '⏱️');
    } else if (state.files.length === 0) {
      const fileInput = document.getElementById('doc-file-input');
      if (fileInput) fileInput.click();
    } else {
      switchView('chat');
    }
  };

  return (
    <DuneContext.Provider
      value={{
        state,
        activeView,
        switchView,
        toast,
        showToast,
        isTaskModalOpen,
        openNewTaskModal,
        closeTaskModal,
        isScheduleModalOpen,
        openAddScheduleModal,
        closeScheduleModal,
        addTask,
        toggleTaskStatus,
        deleteTask,
        addScheduleItem,
        updateScheduleItem,
        deleteScheduleItem,
        executeAppAction,
        deleteFile,
        handleFileUpload,
        askAboutFile,
        saveProfileSettings,
        updateApiKey,
        clearAllData,
        isAiTyping,
        sendChatMessage,
        sendQuickChat,
        handleDashboardActionClick,
        // ChatGPT Multi-Conversation Actions
        createNewChat,
        selectConversation,
        deleteConversation,
        // File Download Actions
        downloadFile,
        downloadTextAsFile
      }}
    >
      {children}
    </DuneContext.Provider>
  );
}

export function useStore() {
  const context = useContext(DuneContext);
  if (!context) {
    throw new Error('useStore must be used within a DuneProvider');
  }
  return context;
}
