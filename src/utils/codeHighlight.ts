function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

const KEYWORDS: Record<string, readonly string[]> = {
  js: [
    'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger', 'default', 'delete',
    'do', 'else', 'export', 'extends', 'finally', 'for', 'function', 'if', 'import', 'in',
    'instanceof', 'let', 'new', 'return', 'super', 'switch', 'this', 'throw', 'try', 'typeof',
    'var', 'void', 'while', 'with', 'yield', 'async', 'await', 'from', 'of', 'as',
  ],
  ts: [
    'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger', 'default', 'delete',
    'do', 'else', 'export', 'extends', 'finally', 'for', 'function', 'if', 'import', 'in',
    'instanceof', 'let', 'new', 'return', 'super', 'switch', 'this', 'throw', 'try', 'typeof',
    'var', 'void', 'while', 'with', 'yield', 'async', 'await', 'from', 'of', 'as', 'interface',
    'type', 'enum', 'implements', 'namespace', 'declare', 'readonly', 'private', 'public',
    'protected', 'abstract', 'keyof', 'infer', 'satisfies',
  ],
  python: [
    'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'def', 'del', 'elif',
    'else', 'except', 'False', 'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try', 'while',
    'with', 'yield',
  ],
  rust: [
    'as', 'async', 'await', 'break', 'const', 'continue', 'crate', 'dyn', 'else', 'enum', 'extern',
    'false', 'fn', 'for', 'if', 'impl', 'in', 'let', 'loop', 'match', 'mod', 'move', 'mut', 'pub',
    'ref', 'return', 'self', 'Self', 'static', 'struct', 'super', 'trait', 'true', 'type', 'unsafe',
    'use', 'where', 'while',
  ],
  bash: [
    'if', 'then', 'else', 'elif', 'fi', 'for', 'while', 'do', 'done', 'case', 'esac', 'function',
    'return', 'in', 'local', 'export', 'source', 'exit', 'set', 'unset',
  ],
  sql: [
    'select', 'from', 'where', 'join', 'inner', 'left', 'right', 'on', 'group', 'by', 'order',
    'having', 'limit', 'insert', 'into', 'values', 'update', 'set', 'delete', 'create', 'table',
    'index', 'and', 'or', 'not', 'null', 'as', 'distinct', 'union', 'all',
  ],
  json: [],
};

const LANG_ALIASES: Record<string, string> = {
  javascript: 'js',
  jsx: 'js',
  typescript: 'ts',
  tsx: 'ts',
  py: 'python',
  rs: 'rust',
  sh: 'bash',
  shell: 'bash',
  zsh: 'bash',
  yml: 'yaml',
  md: 'markdown',
};

function normalizeLang(lang?: string): string {
  if (!lang) return 'plain';
  const key = lang.trim().toLowerCase();
  return LANG_ALIASES[key] ?? key;
}

function getKeywords(lang: string): Set<string> {
  const set = KEYWORDS[lang];
  return set ? new Set(set) : new Set();
}

function span(className: string, text: string): string {
  return `<span class="${className}">${text}</span>`;
}

export function highlightCode(code: string, lang?: string): string {
  const language = normalizeLang(lang);
  const keywords = getKeywords(language);
  let result = escapeHtml(code);
  const placeholders: string[] = [];

  function stash(html: string): string {
    const id = placeholders.length;
    placeholders.push(html);
    return `\x00PH${id}\x00`;
  }

  result = result.replace(/\/\*[\s\S]*?\*\//g, (m) => stash(span('tok-comment', m)));
  result = result.replace(/(^|[^:])\/\/[^\n]*/g, (m, pre) => pre + stash(span('tok-comment', m.slice(pre.length))));
  result = result.replace(/(^|\s)(#[^\n]*)/gm, (_, pre, comment) => pre + stash(span('tok-comment', comment)));
  result = result.replace(
    /(`(?:[^`\\]|\\.)*`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g,
    (m) => stash(span('tok-string', m))
  );

  if (keywords.size) {
    const kwRe = new RegExp(`\\b(${[...keywords].join('|')})\\b`, 'gi');
    result = result.replace(kwRe, (m) => stash(span('tok-keyword', m)));
  }

  result = result.replace(/\b(0x[0-9a-fA-F]+|\d+\.?\d*(?:e[+-]?\d+)?)\b/g, (m) =>
    stash(span('tok-number', m))
  );

  result = result.replace(/\b([A-Z][A-Za-z0-9_]*)\b/g, (m) => {
    if (keywords.has(m) || keywords.has(m.toLowerCase())) return m;
    return stash(span('tok-type', m));
  });

  result = result.replace(/\b([a-z_][\w]*)\s*(?=\()/g, (m) => {
    const name = m.trim().slice(0, -1);
    if (keywords.has(name)) return m;
    return stash(span('tok-function', name)) + ' ';
  });

  result = result.replace(/\x00PH(\d+)\x00/g, (_, id) => placeholders[Number(id)] ?? '');
  return result;
}
