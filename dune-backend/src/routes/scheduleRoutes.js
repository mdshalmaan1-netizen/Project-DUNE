const express = require('express');
const mongoose = require('mongoose');
const Schedule = require('../models/Schedule');
const { authMiddleware } = require('../middleware/auth');

const router = express.Router();
router.use(authMiddleware);

// In-memory fallback if MongoDB is not connected
const fallbackSchedule = new Map();
const isDbConnected = () => mongoose.connection.readyState === 1;

// Default initial schedule for new students
const defaultScheduleItems = [
  { id: 'sched_default_1', title: 'Data Structures & Algorithms', day: 'Mon', time: '10:00', room: 'Hall B - 204' },
  { id: 'sched_default_2', title: 'Operating Systems & Architecture', day: 'Wed', time: '14:00', room: 'Lab 3' },
  { id: 'sched_default_3', title: 'Machine Learning Seminar', day: 'Fri', time: '11:30', room: 'Auditorium 1' }
];

// GET all schedule events
router.get('/', async (req, res) => {
  try {
    const userId = req.user.id;
    if (isDbConnected()) {
      let items = await Schedule.find({ userId }).sort({ createdAt: 1 });
      if (items.length === 0) {
        // Seed initial items for first-time user
        const seeded = await Schedule.insertMany(
          defaultScheduleItems.map(d => ({ ...d, userId, _id: undefined }))
        );
        return res.json(seeded);
      }
      return res.json(items);
    }

    if (!fallbackSchedule.has(userId)) {
      fallbackSchedule.set(userId, [...defaultScheduleItems]);
    }
    res.json(fallbackSchedule.get(userId));
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST add schedule event
router.post('/', async (req, res) => {
  try {
    const userId = req.user.id;
    const { title, day, time, room } = req.body;
    if (!title || !title.trim()) {
      return res.status(400).json({ error: 'Class title is required.' });
    }

    if (isDbConnected()) {
      const item = new Schedule({
        userId,
        title: title.trim(),
        day: day || 'Mon',
        time: time || '09:00',
        room: room ? room.trim() : ''
      });
      await item.save();
      return res.status(201).json(item);
    }

    const newItem = {
      id: 'sched_' + Date.now(),
      userId,
      title: title.trim(),
      day: day || 'Mon',
      time: time || '09:00',
      room: room ? room.trim() : '',
      createdAt: new Date()
    };
    const current = fallbackSchedule.get(userId) || [...defaultScheduleItems];
    current.push(newItem);
    fallbackSchedule.set(userId, current);

    res.status(201).json(newItem);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// PUT update schedule event (by id or by day & time match)
router.put('/update', async (req, res) => {
  try {
    const userId = req.user.id;
    const { id, day, time, title, room } = req.body;
    if (!title || !title.trim()) {
      return res.status(400).json({ error: 'Class title is required.' });
    }

    if (isDbConnected()) {
      let item = null;
      if (id && mongoose.Types.ObjectId.isValid(id)) {
        item = await Schedule.findOne({ _id: id, userId });
      }

      if (!item && day) {
        const dayPrefix = day.slice(0, 3);
        const candidates = await Schedule.find({
          userId,
          day: new RegExp('^' + dayPrefix, 'i')
        });
        if (time && candidates.length > 0) {
          item = candidates.find(c => c.time.replace(/\s+/g, '').includes(time.replace(/\s+/g, '')));
        }
        if (!item && candidates.length > 0) {
          item = candidates[0];
        }
      }

      if (item) {
        item.title = title.trim();
        if (day) item.day = day.slice(0, 3).charAt(0).toUpperCase() + day.slice(1, 3).toLowerCase();
        if (time) item.time = time;
        if (room !== undefined) item.room = room;
        await item.save();
        return res.json(item);
      }

      // If no slot matched, create new
      const newItem = new Schedule({
        userId,
        title: title.trim(),
        day: day ? day.slice(0, 3).charAt(0).toUpperCase() + day.slice(1, 3).toLowerCase() : 'Mon',
        time: time || '10:00',
        room: room || 'Hall B - 204'
      });
      await newItem.save();
      return res.status(201).json(newItem);
    }

    // In-memory fallback
    const current = fallbackSchedule.get(userId) || [...defaultScheduleItems];
    let matched = false;
    const updated = current.map(s => {
      const dayMatch = day ? s.day.toLowerCase().startsWith(day.toLowerCase().slice(0, 3)) : true;
      const timeMatch = time ? s.time.includes(time) : true;
      if (!matched && dayMatch && timeMatch) {
        matched = true;
        return { ...s, title: title.trim(), day: day || s.day, time: time || s.time, room: room || s.room };
      }
      return s;
    });
    if (!matched) {
      updated.push({ id: 'sched_' + Date.now(), userId, title: title.trim(), day: day || 'Mon', time: time || '10:00', room: room || '' });
    }
    fallbackSchedule.set(userId, updated);
    res.json({ message: 'Schedule updated', title });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// DELETE schedule event
router.delete('/:id', async (req, res) => {
  try {
    const userId = req.user.id;
    const itemId = req.params.id;

    if (isDbConnected()) {
      const result = await Schedule.deleteOne({ _id: itemId, userId });
      if (result.deletedCount === 0) {
        return res.status(404).json({ error: 'Schedule item not found.' });
      }
      return res.json({ message: 'Schedule item removed', id: itemId });
    }

    const current = fallbackSchedule.get(userId) || [];
    const filtered = current.filter(s => s.id !== itemId);
    fallbackSchedule.set(userId, filtered);
    res.json({ message: 'Schedule item removed', id: itemId });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
