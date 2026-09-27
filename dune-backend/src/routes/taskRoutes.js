const express = require('express');
const mongoose = require('mongoose');
const Task = require('../models/Task');
const { authMiddleware } = require('../middleware/auth');

const router = express.Router();
router.use(authMiddleware);

// In-memory fallback if MongoDB is not connected
const fallbackTasks = new Map();

// Helper to check MongoDB connection state
const isDbConnected = () => mongoose.connection.readyState === 1;

// GET all tasks
router.get('/', async (req, res) => {
  try {
    const userId = req.user.id;
    if (isDbConnected()) {
      const tasks = await Task.find({ userId }).sort({ createdAt: -1 });
      return res.json(tasks);
    }

    const userTasks = fallbackTasks.get(userId) || [];
    res.json(userTasks);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST create task
router.post('/', async (req, res) => {
  try {
    const userId = req.user.id;
    const { title, priority, due } = req.body;
    if (!title || !title.trim()) {
      return res.status(400).json({ error: 'Task title is required.' });
    }

    if (isDbConnected()) {
      const task = new Task({
        userId,
        title: title.trim(),
        priority: priority || 'med',
        due: due || new Date().toISOString().split('T')[0],
        completed: false
      });
      await task.save();
      return res.status(201).json(task);
    }

    const newTask = {
      id: 'task_' + Date.now(),
      userId,
      title: title.trim(),
      priority: priority || 'med',
      due: due || new Date().toISOString().split('T')[0],
      completed: false,
      createdAt: new Date()
    };
    const userTasks = fallbackTasks.get(userId) || [];
    userTasks.unshift(newTask);
    fallbackTasks.set(userId, userTasks);

    res.status(201).json(newTask);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// PATCH toggle task completed
router.patch('/:id/toggle', async (req, res) => {
  try {
    const userId = req.user.id;
    const taskId = req.params.id;

    if (isDbConnected()) {
      const task = await Task.findOne({ _id: taskId, userId });
      if (!task) return res.status(404).json({ error: 'Task not found.' });

      task.completed = !task.completed;
      await task.save();
      return res.json(task);
    }

    const userTasks = fallbackTasks.get(userId) || [];
    const task = userTasks.find(t => t.id === taskId);
    if (!task) return res.status(404).json({ error: 'Task not found.' });

    task.completed = !task.completed;
    res.json(task);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// DELETE task
router.delete('/:id', async (req, res) => {
  try {
    const userId = req.user.id;
    const taskId = req.params.id;

    if (isDbConnected()) {
      const result = await Task.deleteOne({ _id: taskId, userId });
      if (result.deletedCount === 0) {
        return res.status(404).json({ error: 'Task not found.' });
      }
      return res.json({ message: 'Task deleted successfully', id: taskId });
    }

    const userTasks = fallbackTasks.get(userId) || [];
    const filtered = userTasks.filter(t => t.id !== taskId);
    fallbackTasks.set(userId, filtered);
    res.json({ message: 'Task deleted successfully', id: taskId });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
