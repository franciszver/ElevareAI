// The AI is instructed to emit $...$ / $$...$$ math delimiters (what remark-math
// expects), but LLMs sometimes fall back to \( \) / \[ \] regardless of the prompt.
// Normalize those to $ delimiters so KaTeX still renders the math.
//
// This is a left-to-right scanner (not a count heuristic): it walks the string
// once and pairs each opening delimiter with its nearest correctly-ordered
// closing delimiter of the same kind. Delimiters that never find a matching
// close (truncated/unbalanced input) are left as literal text instead of
// being greedily paired with an unrelated later closer, which would swallow
// all the intervening prose into a single broken math span (KaTeX renders a
// red error in that case).
//
// Escaping uses backslash-RUN PARITY, not a single-character lookback: a
// `\(`/`\[`/`\)`/`\]` is a REAL delimiter iff the run of consecutive
// backslashes immediately preceding the bracket/paren char is ODD (the final
// backslash of the run pairs with the bracket; any earlier backslashes in the
// run are literal text — e.g. two backslashes = one literal escaped
// backslash). This correctly handles runs longer than one, e.g. `\\\(x\\\)`
// (3 backslashes = 1 literal backslash + 1 real delimiter backslash).
//
// Nesting: once we're inside a converted display span (`\[..\]` -> `$$..$$`),
// we do not also convert an inner `\(..\)` to `$..$` — a single `$` inside a
// `$$..$$` span breaks KaTeX parsing. Both display and inline spans are
// located in ORIGINAL-text coordinates, and any inline span that intersects
// a display span is dropped as nested (original coordinates are unambiguous
// here — no re-scanning of the transformed output, which could otherwise
// mis-pair a wrapper `$$` with a literal `$$` inside display-span content).
// The inner literal `\(..\)` is left as-is inside the display span;
// KaTeX/remark-math still renders it correctly as plain LaTeX text within
// the outer $$ block.

// Scan `text` for well-formed backslash-delimiter spans of a single kind
// (`openChar`/`closeChar` are the bare bracket/paren, e.g. '(' / ')'),
// honoring backslash-run parity. Returns an array of { start, end, expr }
// matches (end is exclusive), where `start`/`end` bound the *outer* delimiter
// text (including the delimiters themselves) in original-text coordinates.
function findPairedSpans(text, openChar, closeChar) {
  const spans = [];
  let openIdx = -1;
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (ch === openChar || ch === closeChar) {
      // Count the run of consecutive backslashes immediately before this
      // bracket/paren char.
      let run = 0;
      let j = i - 1;
      while (j >= 0 && text[j] === '\\') {
        run += 1;
        j -= 1;
      }
      if (run % 2 === 1) {
        // Odd run -> real delimiter, starting at the final backslash of
        // the run (the one adjacent to the bracket/paren).
        const delimStart = i - 1;
        if (ch === openChar) {
          // `\( \)` doesn't nest in LaTeX. If we hit a new opener while one
          // is already pending, the earlier opener was a stray/again-opened
          // delimiter — abandon it (leave it as literal text) and track the
          // most recent opener instead, so we don't wrap an unrelated
          // stretch of prose between the abandoned opener and the eventual
          // close.
          openIdx = delimStart;
        } else if (openIdx !== -1) {
          spans.push({ start: openIdx, end: i + 1, expr: text.slice(openIdx + 2, delimStart) });
          openIdx = -1;
        }
      }
    }
    i += 1;
  }
  // Unmatched trailing opener: leave it as literal text (no span emitted).
  return spans;
}

export function normalizeMathDelimiters(text) {
  if (!text) return text;

  // Locate both display (`\[..\]`) and inline (`\(..\)`) spans, both in
  // ORIGINAL-text coordinates.
  const displaySpans = findPairedSpans(text, '[', ']');
  const inlineSpansAll = findPairedSpans(text, '(', ')');

  // Nesting guard: drop any inline span that falls inside a display span.
  // Comparing original-text coordinates is unambiguous, unlike re-deriving
  // a mask from the transformed (`$$`-converted) string.
  const inlineSpans = inlineSpansAll.filter(
    (inline) => !displaySpans.some((d) => inline.start < d.end && inline.end > d.start)
  );

  // Single emit pass over the ORIGINAL text: merge both span lists sorted
  // by start, copying non-span text verbatim.
  const spans = [
    ...displaySpans.map((s) => ({ ...s, wrapper: '$$' })),
    ...inlineSpans.map((s) => ({ ...s, wrapper: '$' })),
  ].sort((a, b) => a.start - b.start);

  let result = '';
  let cursor = 0;
  for (const span of spans) {
    result += text.slice(cursor, span.start);
    result += `${span.wrapper}${span.expr}${span.wrapper}`;
    cursor = span.end;
  }
  result += text.slice(cursor);

  return result;
}
