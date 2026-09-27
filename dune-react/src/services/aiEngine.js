import { escapeHtml } from '../utils/helpers';

// Helper to retrieve active API Key from user state or environment variable
export function getGeminiApiKey(state) {
  if (state?.user?.apiKey && state.user.apiKey.trim()) {
    return state.user.apiKey.trim();
  }
  const envKey = import.meta.env.VITE_GEMINI_API_KEY;
  if (envKey && envKey.trim()) {
    return envKey.trim();
  }
  return null;
}

// Build student context to ground Gemini in real data
function buildStudentContext(state) {
  const contextParts = [];

  if (state?.user) {
    const { name, university, major, semester } = state.user;
    if (name || university || major || semester) {
      contextParts.push(`Student: ${name || 'User'}, Major: ${major || 'N/A'}, University: ${university || 'N/A'}, Semester: ${semester || 'N/A'}`);
    }
  }

  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const todayStr = days[new Date().getDay()];

  if (state?.schedule && state.schedule.length > 0) {
    const todayClasses = state.schedule.filter(s => s.day === todayStr);
    if (todayClasses.length > 0) {
      contextParts.push(`Today's Classes (${todayStr}): ${todayClasses.map(c => `${c.title} (${c.time}, Room: ${c.room || 'General'})`).join(', ')}`);
    } else {
      contextParts.push(`Today's Classes (${todayStr}): None scheduled`);
    }
    contextParts.push(`Weekly Timetable: ${state.schedule.map(c => `[${c.day}] ${c.title} at ${c.time}`).join('; ')}`);
  }

  if (state?.tasks && state.tasks.length > 0) {
    const activeTasks = state.tasks.filter(t => !t.completed);
    if (activeTasks.length > 0) {
      contextParts.push(`Pending Tasks: ${activeTasks.map(t => `"${t.title}" (Due: ${t.due}, Priority: ${t.priority})`).join('; ')}`);
    }
  }

  if (state?.files && state.files.length > 0) {
    contextParts.push(`\n[ALL UPLOADED DOCUMENTS IN "MY FILES" (${state.files.length} documents total)]`);
    state.files.forEach((f, idx) => {
      contextParts.push(`\n======================================================`);
      contextParts.push(`DOCUMENT #${idx + 1}: "${f.name}" (Format: ${f.type || 'FILE'}, Uploaded: ${f.date || 'Recently'})`);
      contextParts.push(`======================================================`);
      if (f.content && f.content.trim()) {
        contextParts.push(`FULL EXTRACTED TEXT CONTENT OF "${f.name}":\n${f.content.slice(0, 60000)}`);
      } else {
        contextParts.push(`(File name: ${f.name} - multimodal visual content attached directly in message)`);
      }
    });
  }

  return contextParts.join('\n');
}

// Direct Grounded Fallback for explicit quick chips when offline/no API key
export function checkDirectGroundedAnswer(prompt, state) {
  const lower = prompt.toLowerCase().trim();

  // Simple Greeting in user's message language
  if (/^(hi|hello|hey|hey there|vanakkam|namaste|greetings|good morning|good afternoon|good evening|yo|sup)\b/i.test(lower) && lower.length < 25) {
    const firstWord = prompt.trim().split(/\s+/)[0];
    const greeting = firstWord.charAt(0).toUpperCase() + firstWord.slice(1);
    if (/vanakkam/i.test(firstWord)) {
      return { text: "Vanakkam! How can I help you today?", citation: "DUNE" };
    }
    if (/namaste/i.test(firstWord)) {
      return { text: "Namaste! How can I help you today?", citation: "DUNE" };
    }
    return { text: `${greeting}! How can I help you today?`, citation: "DUNE" };
  }

  // Explicit Quick Chips
  if (lower === 'my schedule' || lower === 'what is my schedule for today?') {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const todayStr = days[new Date().getDay()];
    const todayClasses = (state.schedule || []).filter(s => s.day === todayStr);
    if (todayClasses.length === 0) {
      return { text: `You have **no classes scheduled for today (${todayStr})**. You are free or can focus on pending assignments!`, citation: "Today's Schedule" };
    }
    let resp = `Here is your schedule for today (**${todayStr}**):\n\n`;
    todayClasses.forEach(c => {
      resp += `• **${c.time}**: ${c.title} (${c.room || 'General'})\n`;
    });
    return { text: resp, citation: "Today's Schedule" };
  }

  if (lower === 'upcoming deadlines' || lower === 'what are my upcoming deadlines?') {
    const activeTasks = (state.tasks || []).filter(t => !t.completed);
    if (activeTasks.length === 0) {
      return { text: "You have **no pending tasks or assignments** right now. Everything is completed! 🎉", citation: "Tasks Manager" };
    }
    let resp = `Here are your **${activeTasks.length} active tasks & upcoming deadlines**:\n\n`;
    activeTasks.forEach((t, i) => {
      resp += `${i + 1}. **${t.title}** — Due: **${t.due}** [${t.priority.toUpperCase()} Priority]\n`;
    });
    return { text: resp, citation: "Tasks Database" };
  }

  // Check if user is explicitly asking to download or receive an uploaded file
  if (state?.files && state.files.length > 0) {
    const matchedFile = state.files.find(f => 
      lower.includes(f.name.toLowerCase()) || 
      lower.includes(f.name.toLowerCase().replace(/\.[^/.]+$/, ""))
    );

    const isExplicitDownload = 
      lower.includes('download') || 
      lower.includes('send file') || 
      lower.includes('send pannu') || 
      lower.includes('file thaa') || 
      lower.includes('file kudu') || 
      lower.includes('file send') ||
      lower.includes('download link') ||
      lower.includes('give me the file') ||
      /\b(download|share file)\b/i.test(lower);

    if (matchedFile && isExplicitDownload) {
      return {
        text: `Kandippa! Inga ungaloda **${matchedFile.name}** file irukku. Keela irukura download button click panni direct-ah download pannikkalam:\n\n[DOWNLOAD:${matchedFile.name}]\n\nIdhula edhavadhu doubts irundha kelunga, naan solli tharen!`,
        citation: `My Files: ${matchedFile.name}`
      };
    }
  }

  if (lower === 'summarize notes' || lower === 'summarize key points from my uploaded files') {
    if ((state.files || []).length > 0) {
      const firstFile = state.files[0];
      if (firstFile && firstFile.content && firstFile.content.trim()) {
        const snippet = firstFile.content.slice(0, 1000);
        return {
          text: `### Analysis & Summary of **${firstFile.name}**\n\n` +
                `**Extracted Highlights:**\n` +
                `> ${snippet.replace(/\n+/g, ' ').slice(0, 400)}...\n\n` +
                `• You have ${state.files.length} document(s) indexed.\n` +
                `• Ask any specific questions about formulas, concepts, or exam questions in this file, or say "send file" to download it!`,
          citation: `File: ${firstFile.name}`
        };
      }
    }
  }

  return null;
}

// Dynamically discover which models are supported by the user's API Key
// Helper to clean leaked model reasoning scratchpads or planning notes
export function cleanModelResponse(text) {
  if (!text) return '';
  let cleaned = text.trim();

  // If the model leaked scratchpad ending with: Let's go with: "..."
  const letsGoWithMatch = cleaned.match(/Let's go with:\s*["“](.*?)["”]\s*$/is);
  if (letsGoWithMatch && letsGoWithMatch[1]) {
    return letsGoWithMatch[1].trim();
  }

  // If the text starts with scratchpad bullet points like * User says: or * Task: or * Language:
  if (cleaned.includes('* User says:') || cleaned.includes('* Language:') || cleaned.includes('* Tone:') || cleaned.includes('* Task:') || cleaned.includes('* Greeting:')) {
    const lines = cleaned.split('\n');
    const filteredLines = [];
    for (const line of lines) {
      const trimmed = line.trim();
      if (/^\*\s*(User says|Language|Tone|Task|Name|User Context|Greeting|Follow-up|Personalization|The user used|I will reply|User's name):/i.test(trimmed)) {
        continue;
      }
      if (/^Let's go with:/i.test(trimmed)) {
        const match = trimmed.match(/^Let's go with:\s*["“]?(.*?)["”]?$/i);
        if (match && match[1]) {
          filteredLines.push(match[1].trim());
        }
        continue;
      }
      if (trimmed.length > 0) {
        filteredLines.push(trimmed);
      }
    }
    if (filteredLines.length > 0) {
      cleaned = filteredLines[filteredLines.length - 1].trim();
    } else {
      cleaned = filteredLines.join('\n').trim();
    }
    if (/^["“](.*)["”]$/s.test(cleaned)) {
      cleaned = cleaned.replace(/^["“](.*)["”]$/s, '$1').trim();
    }
  }

  return cleaned;
}

// Dynamically discover which models are supported by the user's API Key
let modelCache = { key: '', models: [] };

async function getAvailableModels(apiKey) {
  if (modelCache.key === apiKey && modelCache.models.length > 0) {
    return modelCache.models;
  }

  const discovered = [];

  // 1. Try v1beta ListModels
  try {
    const resp = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`);
    if (resp.ok) {
      const data = await resp.json();
      if (data.models && Array.isArray(data.models)) {
        data.models
          .filter(m => m.supportedGenerationMethods && m.supportedGenerationMethods.includes('generateContent'))
          .forEach(m => {
            const rawName = m.name.replace(/^models\//, '');
            discovered.push({ version: 'v1beta', name: rawName });
          });
      }
    }
  } catch (e) {
    console.warn("v1beta ListModels error:", e);
  }

  // 2. Try v1 ListModels
  try {
    const resp = await fetch(`https://generativelanguage.googleapis.com/v1/models?key=${apiKey}`);
    if (resp.ok) {
      const data = await resp.json();
      if (data.models && Array.isArray(data.models)) {
        data.models
          .filter(m => m.supportedGenerationMethods && m.supportedGenerationMethods.includes('generateContent'))
          .forEach(m => {
            const rawName = m.name.replace(/^models\//, '');
            if (!discovered.some(d => d.version === 'v1' && d.name === rawName)) {
              discovered.push({ version: 'v1', name: rawName });
            }
          });
      }
    }
  } catch (e) {
    console.warn("v1 ListModels error:", e);
  }

  // Sort by priority (strictly prioritize full multimodal Gemini models over lite/experimental/gemma models)
  const priorityOrder = [
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-1.5-flash',
    'gemini-1.5-flash-latest',
    'gemini-2.5-pro',
    'gemini-1.5-pro',
    'gemini-1.5-pro-latest',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash-lite-preview',
    'gemini-2.0-flash-lite',
    'gemini-flash-lite-latest',
    'gemini-pro'
  ];

  discovered.sort((a, b) => {
    const indexA = priorityOrder.indexOf(a.name);
    const indexB = priorityOrder.indexOf(b.name);
    const isGeminiA = a.name.startsWith('gemini');
    const isGeminiB = b.name.startsWith('gemini');
    const isLiteA = a.name.includes('lite');
    const isLiteB = b.name.includes('lite');

    const scoreA = indexA !== -1 ? indexA : (isGeminiA ? (isLiteA ? 60 : 30) : 999);
    const scoreB = indexB !== -1 ? indexB : (isGeminiB ? (isLiteB ? 60 : 30) : 999);
    return scoreA - scoreB;
  });

  // Fallback defaults if ListModels call couldn't connect
  if (discovered.length === 0) {
    discovered.push(
      { version: 'v1beta', name: 'gemini-2.0-flash' },
      { version: 'v1beta', name: 'gemini-1.5-flash' },
      { version: 'v1beta', name: 'gemini-1.5-flash-latest' },
      { version: 'v1', name: 'gemini-1.5-flash' },
      { version: 'v1beta', name: 'gemini-pro' }
    );
  }

  modelCache = { key: apiKey, models: discovered };
  return discovered;
}

// Call Google Gemini Cloud API like ChatGPT (Supports English, Tamil, Tanglish, Hindi)
export async function callCloudGemini(prompt, apiKey, state = null) {
  const cleanKey = apiKey.trim();
  const studentContext = state ? buildStudentContext(state) : '';

  const systemInstructionText = 
`You are a natural, friendly, and helpful conversational AI assistant just like ChatGPT for the DUNE student productivity platform.
You speak fluently in English, Tamil, Tanglish (Tamil words in English script), and Hindi.

CRITICAL RULES:
1. Always reply directly and warmly to the user without any internal reasoning, planning notes, or bullet analysis.
2. When the user greets you (e.g. "vanakkam", "namaste", "hello", "hi"):
   - Greet them back warmly in that exact same greeting/language and ask what you can do for them today.
   - Example for "vanakkam": "Vanakkam! How can I help you today?" or "Vanakkam! Epdi irukkeenga? How can I help you today?"
   - Example for "namaste": "Namaste! How can I help you today?"
   - Example for "hello" / "hi": "Hello! How can I help you today?"
3. If the user asks in Tanglish, reply naturally in conversational Tanglish.
4. Output ONLY the direct spoken response to the user.

DOCUMENT & RESUME INTELLIGENCE (TOP PRIORITY):
You have 100% full, deep access to the student's uploaded documents (PDFs, Resumes, CVs, Notes, Syllabus, Assignments) listed below under STUDENT CONTEXT & UPLOADED DOCUMENTS, plus visual pages attached inline.
Whenever the user asks ANY question about an uploaded file or resume:
1. DEEP FACT EXTRACTION:
   - When asked about College, University, Degree, Branch, or Education (e.g. "which college he is studying", "entha college", "college name enna", "what course"):
     * Exhaustively inspect every part of the document: Header, Education section, Affiliations, Institute/College names (e.g. Sri Shakthi Institute of Engineering and Technology, Anna University, etc.), Degree (B.E., B.Tech, M.Tech, M.S., B.Sc), Major/Department, CGPA, and Passing Year.
     * State the EXACT college/institution name, department, and degree directly and clearly.
     * NEVER state that the college name is missing unless you have scrutinized every line and visual element of the document and verified it is truly absent.
   - When asked about Skills, Experience, Projects, or Contact Info:
     * Quote the exact technologies, roles, organizations, and details from the document.
   - When asked for a Summary, Notes, or Concept Explanation:
     * Provide a well-structured breakdown with key takeaways, formulas, and likely exam or interview questions.
2. LANGUAGE MATCHING:
   - If asked in Tanglish, reply naturally in Tanglish (e.g., "Mohammed Shalmaan S vanthu [College Name]-la [Degree] padikiraar pa...").
   - If asked in English or Tamil, reply in that language.

FILE DOWNLOAD RULES:
- ONLY include the tag [DOWNLOAD:filename] (using the exact file name, e.g. [DOWNLOAD:10 Maths Full portion.docx]) when the user EXPLICITLY asks to download, send, get, or export the file/note (for example: "andha file send pannu", "download link kudu", "give me the file to download", "send the document", "maths file thaa").
- DO NOT include [DOWNLOAD:filename] during normal conversation, concept explanations, or when answering questions about the file UNLESS the user explicitly asks to download/send it.
- When the user asks for a downloadable note, revision guide, formula sheet, or summary file, provide the response and end with [DOWNLOAD:notes_filename.txt].

APP CONTROL & LIVE ACTION EXECUTION (FULL ACCESS):
You have 100% FULL ACCESS and DIRECT PERMISSION to make live changes across the DUNE application!
Whenever the user asks you to:
1. Update, change, replace, add, or delete timetable classes/schedules (e.g. "Monday 10am class ah Machine Learning nu maathu", "Add Python class on Friday 9am", "Delete DSA class")
2. Add, complete, or delete tasks/assignments (e.g. "Add assignment due tomorrow", "Mark neural net task completed", "Delete task")
3. Update their student profile (name, semester, major, university)
4. Navigate to another view (e.g. "take me to timetable", "open tasks")

You MUST respond in your friendly, warm, conversational voice (Tanglish/English) confirming the change, AND append the exact executable [ACTION:...] tag at the very end of your response!

ACTION FORMATS:
- Update existing timetable class:
  [ACTION:{"type":"UPDATE_SCHEDULE","day":"Mon","time":"10:00","title":"Machine Learning","room":"Lab 2"}]
  (Use 3-letter day: Mon, Tue, Wed, Thu, Fri, Sat, Sun. Format time as HH:MM like 10:00, 14:00.)
- Add new class to timetable:
  [ACTION:{"type":"ADD_SCHEDULE","day":"Wed","time":"14:00","title":"AI Laboratory","room":"Lab 3"}]
- Delete class from timetable:
  [ACTION:{"type":"DELETE_SCHEDULE","day":"Mon","time":"10:00","title":"Data Structures"}]
- Add a new task:
  [ACTION:{"type":"ADD_TASK","title":"Finish Neural Net Assignment","due":"2026-09-18","priority":"high"}]
- Complete a task:
  [ACTION:{"type":"COMPLETE_TASK","title":"Neural Net"}]
- Delete a task:
  [ACTION:{"type":"DELETE_TASK","title":"Neural Net"}]
- Update student profile:
  [ACTION:{"type":"UPDATE_PROFILE","field":"semester","value":"Semester 5"}]
- Navigate view:
  [ACTION:{"type":"NAVIGATE_VIEW","view":"timetable"}]

CRITICAL RULE:
Keep your spoken message 100% natural, friendly, and conversational like ChatGPT. Append the [ACTION:...] tag at the end.

STUDENT CONTEXT & UPLOADED DOCUMENTS:
${studentContext || 'No student data or files uploaded yet.'}`;

  // Build strictly alternating contents array
  const contents = [];
  const historyPool = (state?.chatHistory || []).filter(m => m.text && m.text.trim());
  let expectedRole = 'user';

  // Take up to 6 previous turns
  const priorMessages = historyPool.slice(-7);
  for (let i = 0; i < priorMessages.length; i++) {
    const msg = priorMessages[i];
    // If it's the current prompt at the end, stop so we append it cleanly
    if (i === priorMessages.length - 1 && msg.role === 'user' && msg.text.trim() === prompt.trim()) {
      break;
    }
    const role = msg.role === 'ai' ? 'model' : 'user';
    if (role === expectedRole) {
      contents.push({
        role: role,
        parts: [{ text: msg.text.trim() }]
      });
      expectedRole = expectedRole === 'user' ? 'model' : 'user';
    }
  }

  // Construct current user parts with multimodal PDF/image attachment if present
  const userParts = [];
  if (state?.files && state.files.length > 0) {
    const lowerPrompt = prompt.toLowerCase();
    const matchedFile = state.files.find(f => lowerPrompt.includes(f.name.toLowerCase().replace(/\.[^/.]+$/, ""))) || state.files[0];
    if (matchedFile?.dataUrl) {
      const match = matchedFile.dataUrl.match(/^data:([a-zA-Z0-9/+-]+);base64,(.+)$/);
      if (match) {
        const mime = match[1];
        const base64Data = match[2];
        if ((mime === 'application/pdf' || mime.startsWith('image/')) && base64Data.length < 25 * 1024 * 1024) {
          userParts.push({
            inlineData: {
              mimeType: mime,
              data: base64Data
            }
          });
        }
      }
    }
  }

  // Always append the current user prompt text
  userParts.push({ text: prompt.trim() });
  contents.push({ role: 'user', parts: userParts });

  // Dynamically query supported models for this specific API key
  const availableModels = await getAvailableModels(cleanKey);
  let lastErrorMessage = '';

  for (const item of availableModels) {
    const { version, name } = item;
    const url = `https://generativelanguage.googleapis.com/${version}/models/${name}:generateContent?key=${cleanKey}`;

    // 1. Try with system_instruction (standard on v1beta for modern models)
    try {
      const payload = {
        system_instruction: {
          parts: [{ text: systemInstructionText }]
        },
        contents: contents,
        generationConfig: {
          temperature: 0.7,
          maxOutputTokens: 3000
        }
      };

      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (resp.ok) {
        const data = await resp.json();
        const reply = data.candidates?.[0]?.content?.parts?.[0]?.text;
        if (reply) {
          return { text: cleanModelResponse(reply), citation: `Gemini AI (${name})` };
        }
      } else {
        const errJson = await resp.json().catch(() => ({}));
        lastErrorMessage = errJson.error?.message || `HTTP ${resp.status}: ${resp.statusText}`;

        // Fallback: If system_instruction or inlineData was rejected, fallback to clean text-only payload
        if (lastErrorMessage.includes('system_instruction') || lastErrorMessage.includes('Unknown name') || lastErrorMessage.includes('inlineData') || lastErrorMessage.includes('mimeType')) {
          const inlineContents = [
            {
              role: 'user',
              parts: [{ text: `${systemInstructionText}\n\nUser Question:\n${prompt}` }]
            }
          ];
          const fbResp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              contents: inlineContents,
              generationConfig: { temperature: 0.7, maxOutputTokens: 3000 }
            })
          });
          if (fbResp.ok) {
            const fbData = await fbResp.json();
            const fbText = fbData.candidates?.[0]?.content?.parts?.[0]?.text;
            if (fbText) {
              return { text: cleanModelResponse(fbText), citation: `Gemini AI (${name})` };
            }
          }
        }
      }
    } catch (err) {
      lastErrorMessage = err.message;
    }
  }

  throw new Error(lastErrorMessage || "Unable to generate content with available Gemini models. Please check your API key.");
}

// Master Response Generator
export async function generateAccurateResponse(userPrompt, state) {
  const apiKey = getGeminiApiKey(state);

  // If Gemini API Key is available, ALWAYS route to live Gemini for ChatGPT-like intelligence
  if (apiKey) {
    try {
      const cloudResp = await callCloudGemini(userPrompt, apiKey, state);
      if (cloudResp) return cloudResp;
    } catch (err) {
      console.error("Gemini Live AI call failed:", err);
      return {
        text: `⚠️ **Google Gemini AI Notice:**\n\n${err.message}\n\n*Please verify your API key using the **⚙️ Manage API Key** button at the top of the chat. You can generate a fresh free key at [Google AI Studio](https://aistudio.google.com/app/apikey).*`,
        citation: "Gemini Connection Error"
      };
    }
  }

  // If NO API Key is connected yet:
  const localAnswer = checkDirectGroundedAnswer(userPrompt, state);
  if (localAnswer) {
    return localAnswer;
  }

  // Helpful Tanglish & English prompt inviting user to connect free Gemini
  return {
    text: `### 🌸 Welcome to DUNE AI (ChatGPT & Tanglish Mode)\n\n` +
          `Machan / Hello! To chat freely like **ChatGPT**, get song lyrics, converse in **Tanglish/Tamil**, solve coding problems, or get help with your coursework:\n\n` +
          `👉 **Please connect your free Google Gemini API Key above:**\n` +
          `1. Click **"🔑 Connect Free Gemini Key"** at the top of this chat.\n` +
          `2. Get a 100% free key from **[aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)** (no credit card needed).\n` +
          `3. Paste and click **Save**!\n\n` +
          `Once connected, I will speak fluent Tanglish & English, provide Tamil cinema songs, debug code, and answer anything! 🚀`,
    citation: "Connect Gemini AI Key"
  };
}
