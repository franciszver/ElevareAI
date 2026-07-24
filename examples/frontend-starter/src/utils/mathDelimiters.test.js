import { describe, it, expect } from 'vitest';
import { normalizeMathDelimiters } from './mathDelimiters';

describe('normalizeMathDelimiters', () => {
  it('converts a simple inline span \\(x^2\\) to $x^2$', () => {
    expect(normalizeMathDelimiters('\\(x^2\\)')).toBe('$x^2$');
  });

  it('converts a simple display span \\[a+b\\] to $$a+b$$', () => {
    expect(normalizeMathDelimiters('\\[a+b\\]')).toBe('$$a+b$$');
  });

  it('leaves plain text with no delimiters unchanged', () => {
    const text = 'Just some plain prose with no math at all.';
    expect(normalizeMathDelimiters(text)).toBe(text);
  });

  it('leaves text already using $ / $$ delimiters unchanged', () => {
    const text = 'Inline $x^2$ and display $$a+b$$ already in KaTeX form.';
    expect(normalizeMathDelimiters(text)).toBe(text);
  });

  it('correctly pairs multiple independent inline spans', () => {
    expect(normalizeMathDelimiters('\\(a\\) and \\(b\\)')).toBe('$a$ and $b$');
  });

  it('does not swallow prose when an opener is re-opened before its close (gap 1)', () => {
    // Old code only checks that total \( count equals total \) count (2 vs 2
    // here — the guard passes) then does a single non-greedy global regex
    // replace. For input containing a re-opened \( before the first one
    // closes, the old regex pairs the FIRST \( with the nearest \), which
    // swallows the second \( (and everything up to the first close) into a
    // single broken math span: '$a \\(b$ c\\)' — a stray backslash-paren
    // ends up *inside* a $..$ span, and a lone \\) is left dangling outside.
    // The correct behavior treats \( as non-nesting: the earlier, abandoned
    // opener is left as literal text, and only the innermost, cleanly
    // paired \(b\) converts — no prose is wrapped into a bogus math span.
    const input = '\\(a \\(b\\) c\\)';
    const expected = '\\(a $b$ c\\)';
    expect(normalizeMathDelimiters(input)).toBe(expected);
  });

  it('does not wrap unrelated prose when a stray unmatched \\( appears before a real pair (gap 1)', () => {
    // A single unmatched \( earlier in the text must not greedily pair with
    // a \) that actually belongs to a later, unrelated \(..\) span.
    const input = 'stray \\( opener with no close, then real math \\(x\\) here';
    const expected = 'stray \\( opener with no close, then real math $x$ here';
    expect(normalizeMathDelimiters(input)).toBe(expected);
  });

  it('does not produce a bare $ inside a $$..$$ span for nested delimiters (gap 2)', () => {
    const input = '\\[ \\frac{a}{b} = \\(c\\) \\]';
    const result = normalizeMathDelimiters(input);
    // The outer display span must convert to $$..$$
    expect(result).toBe('$$ \\frac{a}{b} = \\(c\\) $$');
    // Invariant: no single, unpaired $ inside the $$..$$ span.
    const inner = result.slice(2, -2);
    expect(inner.includes('$')).toBe(false);
  });

  it('leaves an escaped backslash-paren \\\\( ... \\\\) alone (gap 3)', () => {
    const input = 'literal text \\\\(not math\\\\) stays as-is';
    expect(normalizeMathDelimiters(input)).toBe(input);
  });

  it('leaves an escaped backslash-bracket \\\\[ ... \\\\] alone (gap 3)', () => {
    const input = 'literal text \\\\[not math\\\\] stays as-is';
    expect(normalizeMathDelimiters(input)).toBe(input);
  });

  it('leaves an unbalanced, unclosed \\( as literal text (no swallow)', () => {
    const input = 'text with \\( an opener that never closes';
    expect(normalizeMathDelimiters(input)).toBe(input);
  });

  it('leaves an unbalanced, unclosed \\[ as literal text (no swallow)', () => {
    const input = 'text with \\[ an opener that never closes';
    expect(normalizeMathDelimiters(input)).toBe(input);
  });

  it('returns falsy input unchanged', () => {
    expect(normalizeMathDelimiters('')).toBe('');
    expect(normalizeMathDelimiters(null)).toBe(null);
    expect(normalizeMathDelimiters(undefined)).toBe(undefined);
  });

  it('leaves a doubly-escaped backslash-paren \\\\( ... \\\\) literal (2 backslashes = escaped, even)', () => {
    // Sanity-pin for the parity rule: exactly 2 backslashes before the paren
    // is EVEN -> escaped literal backslash, not a delimiter. (This mirrors
    // the existing "gap 3" test above but states the parity rule by name.)
    const BS = '\\'; // one literal backslash character
    const input = `x ${BS.repeat(2)}(y${BS.repeat(2)}) z`;
    expect(normalizeMathDelimiters(input)).toBe(input);
  });

  it('bug 1: odd backslash-run parity — 3 backslashes (literal + real delimiter) converts the real \\( \\)', () => {
    // Old code only checked `text[i-1] === '\\'` (single-char lookback), so
    // a THREE-backslash run before the paren was wrongly treated as escaped
    // and the real, innermost `\(...\)` delimiter was never converted at
    // all. Correct rule: the run of backslashes immediately preceding the
    // bracket/paren is REAL iff its length is ODD (the final backslash
    // pairs with the bracket; any earlier backslashes in the run are
    // literal text). 3 backslashes = 1 literal backslash + 1 real delimiter
    // backslash.
    const BS = '\\'; // one literal backslash character
    const input = `${BS.repeat(3)}(x${BS.repeat(3)})`;
    const result = normalizeMathDelimiters(input);
    // Pin the exact output: the leading/trailing literal backslash pairs
    // are copied through verbatim; only the delimiter's own backslash+
    // bracket pair is consumed and replaced with `$`.
    expect(result).toBe(`${BS.repeat(2)}$x${BS.repeat(2)}$`);
    // Key invariant (in case the exact-leftover-backslash placement above
    // is considered debatable): the delimiter really did convert (an
    // `$...x...$` span exists) and no raw `\(`/`\)` token remains.
    expect(result).toMatch(/\$[^$]*x[^$]*\$/);
    expect(result).not.toContain('\\(');
    expect(result).not.toContain('\\)');
  });

  it('bug 2: nesting mask must use original-text coordinates, not re-derived $$ from transformed output', () => {
    // `\[a $$ \(b\) \]` has a display span whose CONTENT contains a literal
    // `$$` and a nested `\(b\)`. The old code re-scanned the *transformed*
    // string for `$$..$$` pairs to build its nesting mask, so it paired the
    // wrapper `$$` with the literal `$$` inside the content, leaving the
    // nested `\(b\)` outside the (mis-derived) mask and wrongly converting
    // it to `$b$` -> malformed `$$a $$ $b$ $$` (a bare unpaired `$` inside
    // what should be one `$$..$$` span). The fix computes the nesting mask
    // from original-text display-span coordinates (from pass 1), so the
    // nested `\(b\)` is correctly recognized as inside the display span and
    // left untouched.
    const input = '\\[a $$ \\(b\\) \\]';
    const result = normalizeMathDelimiters(input);
    expect(result).toBe('$$a $$ \\(b\\) $$');
    // Invariant: the nested \(b\) must not have been converted.
    expect(result).not.toContain('$b$');
  });

  it('regression: an inline span between two display spans still converts independently', () => {
    const input = '\\[a\\] \\(b\\) \\[c\\]';
    expect(normalizeMathDelimiters(input)).toBe('$$a$$ $b$ $$c$$');
  });
});
