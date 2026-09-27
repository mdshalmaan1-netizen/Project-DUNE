const express = require('express');
const mongoose = require('mongoose');
const Notification = require('../models/Notification');
const { authMiddleware } = require('../middleware/auth');

const router = express.Router();
router.use(authMiddleware);

const isDbConnected = () => mongoose.connection.readyState === 1;
const fallbackNotifs = new Map();

const defaultNotifs = [
  {
    id: 'notif_1',
    title: 'Machine Learning Assignment 3 Due Soon',
    message: 'Neural Network optimization problem set is due in 48 hours.',
    type: 'assignment',
    read: false
  },
  {
    id: 'notif_2',
    title: 'Autonomous Systems Exam Scheduled',
    message: 'Midterm examination scheduled on Friday, Room 402.',
    type: 'exam',
    read: false
  },
  {
    id: 'notif_3',
    title: 'Software Engineering Campus Drive',
    message: 'Internship applications open for upcoming semester campus recruitment.',
    type: 'placement',
    read: false
  }
];

// GET all notifications
router.get('/', async (req, res) => {
  try {
    const userId = req.user.id;
    if (isDbConnected()) {
      let items = await Notification.find({ userId }).sort({ createdAt: -1 });
      if (items.length === 0) {
        const seeded = await Notification.insertMany(
          defaultNotifs.map(n => ({ ...n, userId, _id: undefined }))
        );
        return res.json(seeded);
      }
      return res.json(items);
    }

    if (!fallbackNotifs.has(userId)) {
      fallbackNotifs.set(userId, [...defaultNotifs]);
    }
    res.json(fallbackNotifs.get(userId));
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// PATCH mark notification as read
router.patch('/:id/read', async (req, res) => {
  try {
    const userId = req.user.id;
    const notifId = req.params.id;

    if (isDbConnected()) {
      const notif = await Notification.findOne({ _id: notifId, userId });
      if (notif) {
        notif.read = true;
        await notif.save();
        return res.json(notif);
      }
    }

    const current = fallbackNotifs.get(userId) || [];
    const item = current.find(n => n.id === notifId);
    if (item) item.read = true;
    res.json({ id: notifId, read: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
