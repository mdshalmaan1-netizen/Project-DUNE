const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const User = require('../models/User');
const { authMiddleware } = require('../middleware/auth');

const router = express.Router();
const JWT_SECRET = process.env.JWT_SECRET || 'dune_super_secret_jwt_key_2026';

// Register / Sign Up
router.post('/signup', async (req, res) => {
  try {
    const { name, email, password, university, semester, major } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password are required.' });
    }

    const existingUser = await User.findOne({ email: email.toLowerCase() });
    if (existingUser) {
      return res.status(400).json({ error: 'An account with this email already exists.' });
    }

    const salt = await bcrypt.genSalt(10);
    const hashedPassword = await bcrypt.hash(password, salt);

    const newUser = new User({
      name: name || 'Student',
      email: email.toLowerCase(),
      password: hashedPassword,
      university: university || '',
      semester: semester || '',
      major: major || ''
    });

    await newUser.save();

    const token = jwt.sign(
      { id: newUser._id.toString(), email: newUser.email, name: newUser.name },
      JWT_SECRET,
      { expiresIn: '30d' }
    );

    res.status(201).json({
      user: {
        id: newUser._id.toString(),
        name: newUser.name,
        email: newUser.email,
        university: newUser.university,
        semester: newUser.semester,
        major: newUser.major
      },
      token
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Login
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'Email and password are required.' });
    }

    const user = await User.findOne({ email: email.toLowerCase() });
    if (!user) {
      return res.status(401).json({ error: 'Invalid email or password.' });
    }

    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) {
      return res.status(401).json({ error: 'Invalid email or password.' });
    }

    const token = jwt.sign(
      { id: user._id.toString(), email: user.email, name: user.name },
      JWT_SECRET,
      { expiresIn: '30d' }
    );

    res.json({
      user: {
        id: user._id.toString(),
        name: user.name,
        email: user.email,
        university: user.university,
        semester: user.semester,
        major: user.major,
        apiKey: user.apiKey
      },
      token
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Current User Profile / Settings
router.get('/me', authMiddleware, async (req, res) => {
  try {
    if (req.user.id === 'default-student-1') {
      return res.json({
        id: 'default-student-1',
        name: 'Student',
        email: 'student@dune.edu',
        university: 'University',
        semester: 'Semester 4',
        major: 'Computer Science'
      });
    }

    const user = await User.findById(req.user.id).select('-password');
    if (!user) {
      return res.status(404).json({ error: 'User not found.' });
    }
    res.json(user);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Update Profile & API Key Settings
router.put('/profile', authMiddleware, async (req, res) => {
  try {
    const { name, university, semester, major, apiKey } = req.body;
    if (req.user.id === 'default-student-1') {
      return res.json({
        message: 'Guest profile updated in memory',
        user: { name, university, semester, major, apiKey }
      });
    }

    const user = await User.findById(req.user.id);
    if (!user) return res.status(404).json({ error: 'User not found.' });

    if (name) user.name = name;
    if (university !== undefined) user.university = university;
    if (semester !== undefined) user.semester = semester;
    if (major !== undefined) user.major = major;
    if (apiKey !== undefined) user.apiKey = apiKey;

    await user.save();
    res.json({ message: 'Profile updated successfully', user });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
