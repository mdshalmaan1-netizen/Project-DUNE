const mongoose = require('mongoose');

const ScheduleSchema = new mongoose.Schema({
  userId: { type: String, required: true, index: true },
  title: { type: String, required: true, trim: true },
  day: { type: String, default: 'Mon' },
  time: { type: String, default: '09:00' },
  room: { type: String, default: '' },
  createdAt: { type: Date, default: Date.now }
});

ScheduleSchema.set('toJSON', {
  virtuals: true,
  transform: (doc, ret) => {
    ret.id = ret._id.toString();
    delete ret.__v;
    return ret;
  }
});

module.exports = mongoose.model('Schedule', ScheduleSchema);
