import React from "react";
import { decodeHtmlEntities } from "../utils/clinicalFormatters";
import "./ClinicalContentRenderer.css";

export { decodeHtmlEntities };

/**
 * Parses inline markdown:
 * - Bold: **text** or __text__
 * - Italic: *text* or _text_
 * - Bold+Italic: ***text***
 * - Citations: [S1], [S2, S3]
 * - Inline code: `text`
 */
function parseInlineMarkdown(text, keyPrefix = "inline", enableCitations = true) {
  if (typeof text !== "string" || !text) return null;

  // Pattern matching citations, bold, code, and italic tokens
  const tokenRegex = /(\[S\d+(?:,\s*S\d+)*\]|\*\*\*[^*]+?\*\*\*|\*\*[^*]+?\*\*|__[^_]+?__|`[^`]+?`|\*[^*]+?\*|_[^_]+?_)/g;

  const parts = text.split(tokenRegex);

  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (!part) return null;

    // Clinical Citation [S1], [S2, S3]
    if (enableCitations && /^\[S\d+(?:,\s*S\d+)*\]$/.test(part)) {
      return (
        <span
          key={key}
          className="citation-badge"
          title="Grounded Clinical Source Citation"
        >
          {part}
        </span>
      );
    }

    // Bold + Italic ***text***
    if (part.startsWith("***") && part.endsWith("***") && part.length > 6) {
      return (
        <strong key={key} className="clinical-strong">
          <em className="clinical-em">{part.slice(3, -3)}</em>
        </strong>
      );
    }

    // Bold **text**
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={key} className="clinical-strong">
          {part.slice(2, -2)}
        </strong>
      );
    }

    // Bold __text__
    if (part.startsWith("__") && part.endsWith("__") && part.length > 4) {
      return (
        <strong key={key} className="clinical-strong">
          {part.slice(2, -2)}
        </strong>
      );
    }

    // Inline code `text`
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={key} className="clinical-code">
          {part.slice(1, -1)}
        </code>
      );
    }

    // Italic *text*
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return (
        <em key={key} className="clinical-em">
          {part.slice(1, -1)}
        </em>
      );
    }

    // Italic _text_
    if (part.startsWith("_") && part.endsWith("_") && part.length > 2) {
      return (
        <em key={key} className="clinical-em">
          {part.slice(1, -1)}
        </em>
      );
    }

    return part;
  });
}

/**
 * Universal Clinical Content & Markdown Renderer
 * Safely decodes HTML entities and parses Markdown into well-structured,
 * accessible React components with clean clinical typography.
 */
export default function ClinicalContentRenderer({
  content,
  text,
  inline = false,
  className = "",
  enableCitations = true,
}) {
  const rawInput = content ?? text ?? "";
  if (!rawInput && rawInput !== 0) return null;

  // Ensure string & decode HTML entities first
  const decodedText = decodeHtmlEntities(String(rawInput));

  // If inline mode requested, only render inline elements inside a span
  if (inline) {
    return (
      <span className={`clinical-inline-text ${className}`.trim()}>
        {parseInlineMarkdown(decodedText, "inline", enableCitations)}
      </span>
    );
  }

  // Block Mode: Split into paragraphs and parse headers, lists, and quotes
  const lines = decodedText.split(/\r?\n/);
  const elements = [];
  let currentList = null; // { type: 'ul' | 'ol', items: [] }

  function flushList() {
    if (!currentList) return;
    const ListTag = currentList.type;
    const listIndex = elements.length;
    elements.push(
      <ListTag key={`list-${listIndex}`} className={`clinical-md-${currentList.type}`}>
        {currentList.items.map((item, itemIdx) => (
          <li key={`li-${listIndex}-${itemIdx}`} className="clinical-md-li">
            {parseInlineMarkdown(item, `li-${listIndex}-${itemIdx}`, enableCitations)}
          </li>
        ))}
      </ListTag>
    );
    currentList = null;
  }

  lines.forEach((line, lineIdx) => {
    const trimmed = line.trim();

    // Empty line separates blocks
    if (!trimmed) {
      flushList();
      return;
    }

    // 1. Headers: #, ##, ###, ####
    const headerMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (headerMatch) {
      flushList();
      const level = headerMatch[1].length;
      const headerText = headerMatch[2];
      const HeadingTag = `h${Math.min(level + 2, 6)}`;

      elements.push(
        <HeadingTag key={`h-${lineIdx}`} className={`clinical-md-heading clinical-md-h${level}`}>
          {parseInlineMarkdown(headerText, `h-${lineIdx}`, enableCitations)}
        </HeadingTag>
      );
      return;
    }

    // 2. Unordered Lists: - item, * item, + item
    const ulMatch = trimmed.match(/^[-*+]\s+(.+)$/);
    if (ulMatch) {
      if (!currentList || currentList.type !== "ul") {
        flushList();
        currentList = { type: "ul", items: [] };
      }
      currentList.items.push(ulMatch[1]);
      return;
    }

    // 3. Ordered Lists: 1. item
    const olMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (olMatch) {
      if (!currentList || currentList.type !== "ol") {
        flushList();
        currentList = { type: "ol", items: [] };
      }
      currentList.items.push(olMatch[1]);
      return;
    }

    // 4. Blockquotes: > quote
    const bqMatch = trimmed.match(/^>\s*(.+)$/);
    if (bqMatch) {
      flushList();
      elements.push(
        <blockquote key={`bq-${lineIdx}`} className="clinical-md-blockquote">
          {parseInlineMarkdown(bqMatch[1], `bq-${lineIdx}`, enableCitations)}
        </blockquote>
      );
      return;
    }

    // 5. Standard paragraph line
    flushList();
    elements.push(
      <p key={`p-${lineIdx}`} className="clinical-md-p">
        {parseInlineMarkdown(trimmed, `p-${lineIdx}`, enableCitations)}
      </p>
    );
  });

  // Flush any remaining list
  flushList();

  return (
    <div className={`clinical-content-block ${className}`.trim()}>
      {elements}
    </div>
  );
}

// Re-export as FormattedClinicalText for convenience
export { ClinicalContentRenderer as FormattedClinicalText };
