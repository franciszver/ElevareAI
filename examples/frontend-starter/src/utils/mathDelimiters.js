function countOccurrences(text, substr) {
  return text.split(substr).length - 1;
}

export function normalizeMathDelimiters(text) {
  if (!text) return text;
  let result = text;
  if (countOccurrences(result, '\\[') === countOccurrences(result, '\\]')) {
    result = result.replace(/\\\[([\s\S]*?)\\\]/g, (_, expr) => `$$${expr}$$`);
  }
  if (countOccurrences(result, '\\(') === countOccurrences(result, '\\)')) {
    result = result.replace(/\\\(([\s\S]*?)\\\)/g, (_, expr) => `$${expr}$`);
  }
  return result;
}
