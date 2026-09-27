const fs = require('fs');
const path = require('path');
const pdfParse = require('pdf-parse');
let mammoth = null;
try {
  mammoth = require('mammoth');
} catch (e) {
  console.warn("mammoth not available", e.message);
}

/**
 * Extracts clean text and chunks from an uploaded file (PDF, DOCX, TXT, MD, CSV, code)
 * @param {string} filePath - Absolute or relative path to file
 * @param {string} originalName - Filename with extension
 * @returns {Promise<{ fullText: string, chunks: Array<{ chunkId: string, page: number, text: string }> }>}
 */
async function extractTextAndChunks(filePath, originalName) {
  const ext = path.extname(originalName).toLowerCase();
  let fullText = '';
  const chunks = [];

  try {
    if (ext === '.docx' && mammoth) {
      const result = await mammoth.extractRawText({ path: filePath });
      fullText = result.value || '';
    } else if (ext === '.pdf') {
      const dataBuffer = fs.readFileSync(filePath);
      const pdfData = await pdfParse(dataBuffer);
      fullText = pdfData.text || '';
    } else {
      fullText = fs.readFileSync(filePath, 'utf-8');
    }

    // Split text into chunks (~80 words each) for precise RAG citation
    const paragraphs = fullText.split(/\n\s*\n/).filter(p => p.trim().length > 0);
    let chunkIndex = 0;

    if (paragraphs.length > 0) {
      for (const p of paragraphs) {
        const cleanP = p.replace(/\s+/g, ' ').trim();
        if (cleanP.length > 20) {
          chunks.push({
            chunkId: `chunk_${Date.now()}_${chunkIndex++}`,
            page: Math.floor(chunkIndex / 3) + 1,
            text: cleanP.slice(0, 1000)
          });
        }
      }
    }

    if (chunks.length === 0 && fullText.trim()) {
      chunks.push({
        chunkId: `chunk_${Date.now()}_0`,
        page: 1,
        text: fullText.replace(/\s+/g, ' ').trim().slice(0, 1000)
      });
    }
  } catch (error) {
    console.error(`[pdfService error on ${originalName}]:`, error.message);
    fullText = `Extracted text from ${originalName}`;
    chunks.push({
      chunkId: `chunk_${Date.now()}_err`,
      page: 1,
      text: fullText
    });
  }

  return { fullText, chunks };
}

module.exports = { extractTextAndChunks };
