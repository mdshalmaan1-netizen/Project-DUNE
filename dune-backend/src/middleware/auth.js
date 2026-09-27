const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'dune_super_secret_jwt_key_2026';

const authMiddleware = (req, res, next) => {
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.split(' ')[1];
    try {
      const decoded = jwt.verify(token, JWT_SECRET);
      req.user = {
        id: decoded.id || decoded.userId || 'default-student-1',
        email: decoded.email || 'student@dune.edu',
        name: decoded.name || 'Student'
      };
      return next();
    } catch (err) {
      // Invalid token, fallback gracefully in development
    }
  }

  // Fallback dev user if no token passed
  req.user = {
    id: req.headers['x-user-id'] || 'default-student-1',
    email: 'student@dune.edu',
    name: 'Student'
  };
  next();
};

const requireAuth = (req, res, next) => {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Authentication required. Please login.' });
  }
  const token = authHeader.split(' ')[1];
  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = {
      id: decoded.id || decoded.userId,
      email: decoded.email,
      name: decoded.name
    };
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Invalid or expired token.' });
  }
};

module.exports = { authMiddleware, requireAuth };
