const mongoose = require('mongoose');

const MessageSchema = new mongoose.Schema({
  role: { type: String, enum: ['user', 'ai', 'assistant'], required: true },
  text: { type: String, required: true },
  citation: { type: String, default: '' },
  timestamp: { type: Date, default: Date.now }
}, { _id: false });

const ConversationSchema = new mongoose.Schema({
  userId: { type: String, required: true, index: true },
  title: { type: String, default: 'New Conversation' },
  messages: [MessageSchema],
  createdAt: { type: String, default: () => new Date().toLocaleDateString() },
  updatedAt: { type: Date, default: Date.now }
});

ConversationSchema.set('toJSON', {
  virtuals: true,
  transform: (doc, ret) => {
    ret.id = ret._id.toString();
    delete ret.__v;
    return ret;
  }
});

module.exports = mongoose.model('Conversation', ConversationSchema);
