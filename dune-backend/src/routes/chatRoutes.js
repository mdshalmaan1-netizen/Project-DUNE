const express = require('express');
const mongoose = require('mongoose');
const Conversation = require('../models/Conversation');
const User = require('../models/User');
const { authMiddleware } = require('../middleware/auth');
const { generateAIResponse } = require('../services/aiService');

const router = express.Router();
router.use(authMiddleware);

const isDbConnected = () => mongoose.connection.readyState === 1;
const fallbackConversations = new Map();

// GET all conversations
router.get('/conversations', async (req, res) => {
  try {
    const userId = req.user.id;
    if (isDbConnected()) {
      const convs = await Conversation.find({ userId }).sort({ updatedAt: -1 });
      return res.json(convs);
    }

    const list = fallbackConversations.get(userId) || [];
    res.json(list);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// GET single conversation
router.get('/conversations/:id', async (req, res) => {
  try {
    const userId = req.user.id;
    const convId = req.params.id;

    if (isDbConnected()) {
      const conv = await Conversation.findOne({ _id: convId, userId });
      if (!conv) return res.status(404).json({ error: 'Conversation not found.' });
      return res.json(conv);
    }

    const list = fallbackConversations.get(userId) || [];
    const conv = list.find(c => c.id === convId);
    if (!conv) return res.status(404).json({ error: 'Conversation not found.' });
    res.json(conv);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// DELETE conversation
router.delete('/conversations/:id', async (req, res) => {
  try {
    const userId = req.user.id;
    const convId = req.params.id;

    if (isDbConnected()) {
      await Conversation.deleteOne({ _id: convId, userId });
      return res.json({ message: 'Conversation deleted', id: convId });
    }

    const list = fallbackConversations.get(userId) || [];
    fallbackConversations.set(userId, list.filter(c => c.id !== convId));
    res.json({ message: 'Conversation deleted', id: convId });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST send chat message (Main AI Agent pipeline)
router.post('/', async (req, res) => {
  try {
    const userId = req.user.id;
    const { prompt, conversationId, history = [], apiKey = '' } = req.body;

    if (!prompt || !prompt.trim()) {
      return res.status(400).json({ error: 'Message text is required.' });
    }

    // Fetch user profile if available
    let userObj = { id: userId, name: req.user.name || 'Student' };
    if (isDbConnected() && userId !== 'default-student-1') {
      const dbUser = await User.findById(userId).lean();
      if (dbUser) userObj = { ...dbUser, id: userId };
    }

    // Generate AI response with RAG
    const aiResult = await generateAIResponse({
      query: prompt.trim(),
      user: userObj,
      history,
      apiKey: apiKey || userObj.apiKey
    });

    const userMessage = { role: 'user', text: prompt.trim(), timestamp: new Date() };
    const aiMessage = {
      role: 'ai',
      text: aiResult.text,
      citation: aiResult.citation,
      timestamp: new Date()
    };

    let activeConvId = conversationId;

    if (isDbConnected()) {
      let conv = null;
      if (conversationId && mongoose.Types.ObjectId.isValid(conversationId)) {
        conv = await Conversation.findOne({ _id: conversationId, userId });
      }

      if (!conv) {
        // Create new conversation
        const title = prompt.trim().slice(0, 32) + (prompt.trim().length > 32 ? '...' : '');
        conv = new Conversation({
          userId,
          title,
          messages: [userMessage, aiMessage]
        });
        await conv.save();
        activeConvId = conv._id.toString();
      } else {
        // Append messages
        conv.messages.push(userMessage, aiMessage);
        conv.updatedAt = new Date();
        await conv.save();
        activeConvId = conv._id.toString();
      }
    } else {
      // In-memory fallback
      let list = fallbackConversations.get(userId) || [];
      let conv = list.find(c => c.id === conversationId);

      if (!conv) {
        activeConvId = 'conv_' + Date.now();
        conv = {
          id: activeConvId,
          userId,
          title: prompt.trim().slice(0, 32) + (prompt.trim().length > 32 ? '...' : ''),
          messages: [userMessage, aiMessage],
          createdAt: new Date().toLocaleDateString(),
          updatedAt: new Date()
        };
        list.unshift(conv);
      } else {
        conv.messages.push(userMessage, aiMessage);
        conv.updatedAt = new Date();
      }
      fallbackConversations.set(userId, list);
    }

    res.json({
      role: 'ai',
      text: aiResult.text,
      citation: aiResult.citation,
      citations: aiResult.citations,
      conversationId: activeConvId
    });
  } catch (error) {
    console.error('[Chat route error]:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
