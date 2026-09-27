const Document = require('../models/Document');

/**
 * Searches indexed documents for relevant chunks (RAG)
 */
async function searchDocumentChunks(userId, query) {
  try {
    const tokens = query.toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .split(/\s+/)
      .filter(t => t.length > 3 && !['what', 'when', 'where', 'which', 'about', 'explain', 'tell', 'please', 'this', 'that'].includes(t));

    if (tokens.length === 0) return { citations: [], contextText: '' };

    const docs = await Document.find({ userId }).lean();
    const matches = [];

    for (const doc of docs) {
      if (!doc.chunks || doc.chunks.length === 0) continue;
      for (const chunk of doc.chunks) {
        const textLower = chunk.text.toLowerCase();
        let score = 0;
        for (const token of tokens) {
          if (textLower.includes(token)) score++;
        }
        if (score > 0) {
          matches.push({
            title: doc.name,
            page: chunk.page || 1,
            snippet: chunk.text.slice(0, 160) + '...',
            fullText: chunk.text,
            score
          });
        }
      }
    }

    matches.sort((a, b) => b.score - a.score);
    const topMatches = matches.slice(0, 4);

    const citations = topMatches.map(m => ({
      title: m.title,
      page: m.page,
      snippet: m.snippet
    }));

    const contextText = topMatches.map(m => `[From Document "${m.title}", Page ${m.page}]:\n${m.fullText}`).join('\n\n');

    return { citations, contextText };
  } catch (error) {
    console.error('[RAG search error]:', error.message);
    return { citations: [], contextText: '' };
  }
}

/**
 * Calls Gemini REST API
 */
async function callGemini(prompt, systemInstruction, apiKey, history = []) {
  const models = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-pro'];
  
  const contents = [];
  if (history && history.length > 0) {
    for (const msg of history.slice(-10)) {
      const role = (msg.role === 'user' || msg.role === 'human') ? 'user' : 'model';
      if (msg.text && msg.text.trim()) {
        contents.push({ role, parts: [{ text: msg.text }] });
      }
    }
  }
  contents.push({ role: 'user', parts: [{ text: prompt }] });

  for (const model of models) {
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents,
          systemInstruction: { parts: [{ text: systemInstruction }] },
          generationConfig: { temperature: 0.7, maxOutputTokens: 2048 }
        })
      });

      if (response.ok) {
        const data = await response.json();
        const candidate = data.candidates?.[0]?.content?.parts?.[0]?.text;
        if (candidate) return candidate;
      }
    } catch (e) {
      console.warn(`[Gemini ${model} request failed]:`, e.message);
    }
  }

  return null;
}

/**
 * High-quality fallback intelligence when offline or without Gemini API key
 */
function localIntelligence(query, user, contextText, citations) {
  const q = query.toLowerCase().trim();
  const userName = user?.name || 'Student';

  // If RAG context matched uploaded files
  if (contextText && citations.length > 0) {
    return `### 📚 Answer from your Indexed Documents\n\nBased on your course materials (**${citations[0].title}**, Page ${citations[0].page}):\n\n${citations.map(c => `> "${c.snippet}"\n*(Source: ${c.title}, p. ${c.page})*`).join('\n\n')}\n\n**Key Takeaways & Study Recommendations:**\n- Review this section carefully before your next assignment or quiz.\n- Highlight the core definitions and formulas noted above.\n- Let me know if you would like practice quiz questions generated from this document!`;
  }

  // Simple Greetings in user's message language
  if (/^(hi|hello|hey|hey there|vanakkam|namaste|greetings|good morning|good afternoon|good evening|yo|sup)\b/i.test(q) && q.length < 25) {
    const firstWord = query.trim().split(/\s+/)[0];
    const greeting = firstWord.charAt(0).toUpperCase() + firstWord.slice(1);
    if (/vanakkam/i.test(firstWord)) {
      return `Vanakkam! How can I help you today?`;
    }
    if (/namaste/i.test(firstWord)) {
      return `Namaste! How can I help you today?`;
    }
    return `${greeting}! How can I help you today?`;
  }

  // Schedule & Timetable questions
  if (q.includes('schedule') || q.includes('timetable') || q.includes('class')) {
    return `📅 **Schedule Management:**\n\nYou can view and customize your full weekly lecture schedule in the **Timetable** tab.\n\nWould you like me to check your classes for today?`;
  }

  // Assignments and Tasks
  if (q.includes('task') || q.includes('assignment') || q.includes('homework') || q.includes('deadline')) {
    return `✅ **Academic Tasks:**\n\nYou can view and organize all your upcoming deadlines in the **Tasks** tab.\n\nWould you like to add a new task or review pending deadlines?`;
  }

  // Conversational response
  if (/ena pandr|enna panr|enna pandr|what are you doing/i.test(q)) {
    return `Onnum illa! Ungalukku help panna ready-ah irukken. Enna pannanum sollunga? 😊`;
  }

  return `Sollunga! Ungalukku naan enna panna mudiyum? How can I help you today?`;
}

/**
 * Main AI Generation Pipeline
 */
async function generateAIResponse({ query, user, history = [], apiKey = '' }) {
  const effectiveApiKey = apiKey || process.env.GEMINI_API_KEY || '';
  const { citations, contextText } = await searchDocumentChunks(user?.id || 'default-student-1', query);

  const systemPrompt = `You are DUNE, a friendly, concise, natural AI academic assistant.
You speak fluently in English, Tamil, Tanglish (Tamil in English script), and Hindi.

CRITICAL RULES:
1. When the user simply greets you (e.g. "hi", "hello", "hey", "vanakkam", "namaste"):
   - Greet back in the EXACT same language and ask what you can do for them.
   - Example for "hi": "Hi! How can I help you today?"
   - Example for "vanakkam": "Vanakkam! How can I help you today?"
   - Example for "namaste": "Namaste! How can I help you today?"
   - NEVER output bulleted lists of features, capabilities, or boilerplate promotional text.
2. If the user asks in Tanglish, reply naturally in conversational Tanglish.
3. Be concise, direct, and conversational.
${contextText ? `\nRELEVANT COURSE DOCUMENTS:\n${contextText}\nCite relevant document titles and pages when answering from these documents.` : ''}`;

  let responseText = null;

  if (effectiveApiKey) {
    responseText = await callGemini(query, systemPrompt, effectiveApiKey, history);
  }

  if (!responseText) {
    responseText = localIntelligence(query, user, contextText, citations);
  }

  return {
    text: responseText,
    citations,
    citation: citations.length > 0 ? `${citations[0].title} (p. ${citations[0].page})` : 'DUNE Academic Engine'
  };
}

module.exports = { generateAIResponse, searchDocumentChunks };
