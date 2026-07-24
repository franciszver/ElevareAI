// The AI is instructed to emit $...$ / $$...$$ math delimiters (what remark-math
// expects), but LLMs sometimes fall back to \( \) / \[ \] regardless of the prompt.
// Normalize those to $ delimiters so KaTeX still renders the math.
//
// This is a left-to-right scanner (not a count heuristic): it walks the string
// once, tracks backslash-escape state so a literal `\\(` (escaped backslash
// followed by a paren) is never mistaken for a delimiter, and pairs each
// opening delimiter with its nearest correctly-ordered closing delimiter of the
// same kind. Delimiters that never find a matching close (truncated/unbalanced
// input) are left as literal text instead of being greedily paired with an
// unrelated later closer, which would swallow all the intervening prose into a
// single broken math span (KaTeX renders a red error in that case).
//
// Nesting: once we're inside a converted display span (`\[..\]` -> `$$..$$`),
// we do not also convert an inner `\(..\)` to `$..$` — a single `$` inside a
// `$$..$$` span breaks KaTeX parsing. The inner literal `\(..\)` is left as-is
// inside the display span; KaTeX/remark-math still renders it correctly as
// plain LaTeX text within the outer $$ block.

// Scan `text` for well-formed `open ... close` spans of a single delimiter
// kind, honoring backslash-escaping. Returns an array of { start, end, expr }
// matches (end is exclusive), where `start`/`end` bound the *outer* delimiter
// text (including the delimiters themselves).
function findPairedSpans(text, open, close) {
  const spans = [];
  let i = 0;
  let openIdx = -1;
  while (i < text.length) {
    // A delimiter preceded by a backslash is an escaped literal (`\\(`),
    // not a real delimiter — skip it.
    const precedingBackslash = text[i - 1] === '\\';
    if (!precedingBackslash && text.startsWith(open, i)) {
      // `\( \)` doesn't nest in LaTeX. If we hit a new opener while one is
      // already pending, the earlier opener was a stray/again-opened
      // delimiter — abandon it (leave it as literal text) and track the
      // most recent opener instead, so we don't wrap an unrelated stretch
      // of prose between the abandoned opener and the eventual close.
      openIdx = i;
      i += open.length;
      continue;
    }
    if (!precedingBackslash && openIdx !== -1 && text.startsWith(close, i)) {
      spans.push({ start: openIdx, end: i + close.length, expr: text.slice(openIdx + open.length, i) });
      openIdx = -1;
      i += close.length;
      continue;
    }
    i += 1;
  }
  // Unmatched trailing opener: leave it as literal text (no span emitted).
  return spans;
}

export function normalizeMathDelimiters(text) {
  if (!text) return text;

  // Pass 1: find and convert `\[..\]` display-math spans.
  const displaySpans = findPairedSpans(text, '\\[', '\\]');

  let result = '';
  let cursor = 0;
  for (const span of displaySpans) {
    result += text.slice(cursor, span.start);
    result += `$$${span.expr}$$`;
    cursor = span.end;
  }
  result += text.slice(cursor);

  // Pass 2: find and convert `\(..\)` inline-math spans, but skip any that
  // fall inside a display span we just converted (nesting guard) — those
  // characters are still `\(..\)` in `result` since pass 1 didn't touch them.
  // Mask out the already-converted `$$..$$` regions before scanning for `\(`.
  const maskedRanges = [];
  {
    let idx = 0;
    while (idx < result.length) {
      const start = result.indexOf('$$', idx);
      if (start === -1) break;
      const end = result.indexOf('$$', start + 2);
      if (end === -1) break;
      maskedRanges.push([start, end + 2]);
      idx = end + 2;
    }
  }
  const isMasked = (pos) => maskedRanges.some(([s, e]) => pos >= s && pos < e);

  const inlineSpans = findPairedSpans(result, '\\(', '\\)').filter(
    (span) => !isMasked(span.start)
  );

  let finalResult = '';
  cursor = 0;
  for (const span of inlineSpans) {
    finalResult += result.slice(cursor, span.start);
    finalResult += `$${span.expr}$`;
    cursor = span.end;
  }
  finalResult += result.slice(cursor);

  return finalResult;
}
