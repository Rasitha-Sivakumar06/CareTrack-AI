/**
 * Clinical text and Markdown formatting utilities for CareTrack AI.
 * Handles:
 * - HTML entity decoding (decimal &#76;, hex &#x4C;, named &amp;, etc.)
 * - Text sanitization and normalization
 * - Speech text cleaning (preserving clinical figures while stripping markup)
 */

/**
 * Robust HTML entity decoder.
 * Supports:
 * - Hexadecimal entities (e.g. &#x4C; -> 'L', &#x20; -> ' ')
 * - Decimal numeric entities (e.g. &#76; -> 'L', &#39; -> "'")
 * - Common named HTML entities (&amp;, &quot;, &lt;, &gt;, &deg;, &plusmn;, etc.)
 * - Browser DOMParser fallback for extended/obscure entities
 */
export function decodeHtmlEntities(rawText) {
  if (typeof rawText !== "string" || !rawText) return rawText ?? "";

  // Quick exit if no ampersand present
  if (!rawText.includes("&")) return rawText;

  // 1. Decode hexadecimal entities: &#x4C; -> L
  let decoded = rawText.replace(/&#x([0-9a-fA-F]+);/g, (match, hex) => {
    try {
      const code = parseInt(hex, 16);
      return String.fromCodePoint ? String.fromCodePoint(code) : String.fromCharCode(code);
    } catch {
      return match;
    }
  });

  // 2. Decode decimal numeric entities: &#76; -> L, &#39; -> '
  decoded = decoded.replace(/&#(\d+);/g, (match, dec) => {
    try {
      const code = parseInt(dec, 10);
      return String.fromCodePoint ? String.fromCodePoint(code) : String.fromCharCode(code);
    } catch {
      return match;
    }
  });

  // 3. Common named entities dictionary
  const namedEntities = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&apos;": "'",
    "&nbsp;": " ",
    "&deg;": "°",
    "&plusmn;": "±",
    "&bull;": "•",
    "&ndash;": "–",
    "&mdash;": "—",
    "&rarr;": "→",
    "&larr;": "←",
    "&uarr;": "↑",
    "&darr;": "↓",
    "&check;": "✓",
    "&times;": "×",
    "&hellip;": "…",
  };

  decoded = decoded.replace(
    /&(?:amp|lt|gt|quot|apos|nbsp|deg|plusmn|bull|ndash|mdash|rarr|larr|uarr|darr|check|times|hellip);/g,
    (entity) => namedEntities[entity] ?? entity
  );

  // 4. Browser DOM fallback for remaining arbitrary HTML entities if any
  if (typeof document !== "undefined" && decoded.includes("&")) {
    try {
      const parser = new DOMParser();
      const doc = parser.parseFromString(decoded, "text/html");
      if (doc && doc.body) {
        decoded = doc.body.textContent || decoded;
      }
    } catch {
      // safe fallback if DOMParser fails
    }
  }

  return decoded;
}

/**
 * Strips markup for voice synthesis while preserving clinical numbers and observations.
 */
export function cleanTextForSpeech(text) {
  if (!text) return "";
  const decoded = decodeHtmlEntities(String(text));
  return decoded
    // Remove citations like [S1], [S2, S3]
    .replace(/\[S\d+(?:,\s*S\d+)*\]/g, "")
    // Remove markdown links [title](url) -> title
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    // Remove markdown bold/italics
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    // Remove markdown headers
    .replace(/^#{1,6}\s+/gm, "")
    // Remove blockquotes and list bullets
    .replace(/^>\s+/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    // Remove code blocks and inline code
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    // Remove HTML tags if any
    .replace(/<[^>]*>/g, "")
    // Normalize whitespace around punctuation
    .replace(/\s+([.,;:!?])/g, "$1")
    // Normalize whitespace
    .replace(/\s+/g, " ")
    .trim();
}
