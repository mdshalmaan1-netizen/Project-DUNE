const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const mongoose = require('mongoose');
const Document = require('../models/Document');
const { authMiddleware } = require('../middleware/auth');
const { extractTextAndChunks } = require('../services/pdfService');

const router = express.Router();
router.use(authMiddleware);

// Ensure upload directory exists
const UPLOAD_DIR = path.join(__dirname, '../../student_uploads');
if (!fs.existsSync(UPLOAD_DIR)) {
  fs.mkdirSync(UPLOAD_DIR, { recursive: true });
}

// Configure Multer storage
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, UPLOAD_DIR);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, uniqueSuffix + '-' + file.originalname.replace(/[^a-zA-Z0-9._-]/g, '_'));
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 25 * 1024 * 1024 } // 25MB max
});

const isDbConnected = () => mongoose.connection.readyState === 1;
const fallbackDocs = new Map();

// GET all documents
router.get('/', async (req, res) => {
  try {
    const userId = req.user.id;
    if (isDbConnected()) {
      const docs = await Document.find({ userId })
        .select('-chunks.text') // Exclude heavy raw text for list performance
        .sort({ createdAt: -1 });
      return res.json(docs);
    }

    const list = fallbackDocs.get(userId) || [];
    res.json(list.map(d => ({ ...d, chunks: undefined })));
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// POST upload & index document
router.post('/upload', upload.single('file'), async (req, res) => {
  try {
    const userId = req.user.id;
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded.' });
    }

    const { fullText, chunks } = await extractTextAndChunks(req.file.path, req.file.originalname);
    const fileExt = path.extname(req.file.originalname).replace('.', '').toUpperCase();

    if (isDbConnected()) {
      const doc = new Document({
        userId,
        name: req.file.originalname,
        type: fileExt || 'PDF',
        filePath: req.file.path,
        fileSize: req.file.size,
        date: new Date().toLocaleDateString(),
        content: fullText.slice(0, 20000), // Preview text
        chunkCount: chunks.length,
        chunks
      });

      await doc.save();
      return res.status(201).json(doc);
    }

    const newDoc = {
      id: 'doc_' + Date.now(),
      userId,
      name: req.file.originalname,
      type: fileExt || 'PDF',
      filePath: req.file.path,
      fileSize: req.file.size,
      date: new Date().toLocaleDateString(),
      content: fullText.slice(0, 20000),
      chunkCount: chunks.length,
      chunks,
      createdAt: new Date()
    };
    const current = fallbackDocs.get(userId) || [];
    current.unshift(newDoc);
    fallbackDocs.set(userId, current);

    res.status(201).json(newDoc);
  } catch (error) {
    console.error('[Upload error]:', error);
    res.status(500).json({ error: error.message });
  }
});

// GET download file
router.get('/:id/download', async (req, res) => {
  try {
    const userId = req.user.id;
    const docId = req.params.id;

    let doc = null;
    if (isDbConnected()) {
      doc = await Document.findOne({ _id: docId, userId });
    } else {
      const current = fallbackDocs.get(userId) || [];
      doc = current.find(d => d.id === docId);
    }

    if (!doc) return res.status(404).json({ error: 'Document not found.' });

    if (doc.filePath && fs.existsSync(doc.filePath)) {
      return res.download(doc.filePath, doc.name);
    }

    // Fallback: send text content as a download
    res.setHeader('Content-disposition', `attachment; filename="${doc.name}.txt"`);
    res.setHeader('Content-type', 'text/plain');
    res.send(doc.content || 'No content');
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// DELETE document
router.delete('/:id', async (req, res) => {
  try {
    const userId = req.user.id;
    const docId = req.params.id;

    if (isDbConnected()) {
      const doc = await Document.findOne({ _id: docId, userId });
      if (!doc) return res.status(404).json({ error: 'Document not found.' });

      if (doc.filePath && fs.existsSync(doc.filePath)) {
        try { fs.unlinkSync(doc.filePath); } catch (e) { /* ignore */ }
      }

      await Document.deleteOne({ _id: docId });
      return res.json({ message: 'Document deleted successfully', id: docId });
    }

    const current = fallbackDocs.get(userId) || [];
    const found = current.find(d => d.id === docId);
    if (found && found.filePath && fs.existsSync(found.filePath)) {
      try { fs.unlinkSync(found.filePath); } catch (e) { /* ignore */ }
    }
    fallbackDocs.set(userId, current.filter(d => d.id !== docId));
    res.json({ message: 'Document deleted successfully', id: docId });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
