const mongoose = require('mongoose');

const DocumentChunkSchema = new mongoose.Schema({
  chunkId: { type: String, required: true },
  page: { type: Number, default: 1 },
  text: { type: String, required: true }
}, { _id: false });

const DocumentSchema = new mongoose.Schema({
  userId: { type: String, required: true, index: true },
  name: { type: String, required: true },
  type: { type: String, default: 'PDF' },
  filePath: { type: String, default: '' },
  fileSize: { type: Number, default: 0 },
  date: { type: String, default: () => new Date().toLocaleDateString() },
  content: { type: String, default: '' },
  chunkCount: { type: Number, default: 0 },
  chunks: [DocumentChunkSchema],
  createdAt: { type: Date, default: Date.now }
});

DocumentSchema.set('toJSON', {
  virtuals: true,
  transform: (doc, ret) => {
    ret.id = ret._id.toString();
    delete ret.__v;
    return ret;
  }
});

module.exports = mongoose.model('Document', DocumentSchema);
