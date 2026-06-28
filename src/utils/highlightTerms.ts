const STOP_WORDS = new Set([
  'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one',
  'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old',
  'see', 'two', 'way', 'who', 'did', 'let', 'say', 'she', 'too', 'use', 'what', 'when', 'where',
  'which', 'with', 'have', 'this', 'that', 'from', 'they', 'will', 'your', 'about', 'into',
  'some', 'them', 'than', 'then', 'also', 'just', 'like', 'more', 'most', 'other', 'such',
  '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也',
  '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '什么',
  '怎么', '如何', '为什么', '可以', '吗', '呢', '吧', '啊', '请', '帮', '帮我', '告诉', '查询',
  '搜索', '一下', '知道', '介绍',
]);

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function extractSearchTerms(text: string): string[] {
  const terms = new Set<string>();
  const trimmed = text.trim();
  if (!trimmed) return [];

  for (const match of trimmed.matchAll(/["'""'']([^"'""'']{2,})["'""'']/g)) {
    const phrase = match[1]?.trim();
    if (phrase && phrase.length >= 2 && !STOP_WORDS.has(phrase)) {
      terms.add(phrase);
    }
  }

  for (const match of trimmed.matchAll(/[\u4e00-\u9fff]{2,8}/g)) {
    const word = match[0];
    if (!STOP_WORDS.has(word)) terms.add(word);
  }

  for (const match of trimmed.matchAll(/[a-zA-Z][a-zA-Z0-9+.#_-]{2,}/g)) {
    const word = match[0];
    if (!STOP_WORDS.has(word.toLowerCase())) terms.add(word);
  }

  return [...terms]
    .filter((term) => term.length >= 2)
    .sort((a, b) => b.length - a.length)
    .slice(0, 16);
}

export function highlightTermsInHtml(html: string, terms: string[]): string {
  const filtered = terms.filter((term) => term.trim().length >= 2);
  if (!filtered.length) return html;

  const pattern = new RegExp(`(${filtered.map(escapeRegex).join('|')})`, 'gi');
  const segments = html.split(/(<(?:pre|code)[^>]*>[\s\S]*?<\/(?:pre|code)>)/gi);

  return segments
    .map((segment) => {
      if (/^<(pre|code)/i.test(segment)) return segment;
      return segment.replace(pattern, '<mark class="md-search-hit">$1</mark>');
    })
    .join('');
}
