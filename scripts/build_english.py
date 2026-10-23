"""Build English siblings from Chinese HTML and reviewed exact-string translations."""
import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://gregorytsai.github.io/mac-studio-m3-ultra-mtp-benchmark/'
PAGES = ['index.html', 'analysis.html', 'resources.html']
CJK = re.compile(r'[\u3400-\u9fff]')

def english_name(name):
    return name.replace('.html', '-en.html')

def alternates(name):
    zh = SITE + ('' if name == 'index.html' else name)
    en = SITE + english_name(name)
    return ''.join(f'<link rel="alternate" hreflang="{lang}" href="{url}">' for lang, url in [('zh-Hant', zh), ('en', en), ('x-default', zh)])

class Translator(HTMLParser):
    def __init__(self, translations, name):
        super().__init__(convert_charrefs=False)
        self.translations, self.name, self.parts = translations, name, []

    def translate(self, value):
        if CJK.search(value):
            if value not in self.translations:
                raise ValueError('Missing English translation: ' + value)
            return self.translations[value]
        return value

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for key, value in attrs:
            if value is None:
                continue
            value = self.translate(value)
            if tag == 'html' and key == 'lang':
                value = 'en'
            if key == 'href':
                for page in PAGES:
                    if value == page or value.startswith(page + '#'):
                        value = value.replace(page, english_name(page), 1)
                        break
                if values.get('rel') == 'canonical':
                    value = SITE + english_name(self.name)
            if key == 'src' and value.startswith('assets/explore.js'):
                digest = hashlib.sha256((ROOT/'assets/explore-en.js').read_bytes()).hexdigest()[:10]
                value = 'assets/explore-en.js?v=' + digest
            values[key] = value
        self.parts.append('<' + tag + ''.join(' ' + key + ('' if value is None else '="' + html.escape(value, quote=True) + '"') for key, value in values.items()) + '>')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.parts[-1] = self.parts[-1][:-1] + '/>'

    def handle_endtag(self, tag):
        self.parts.append('</' + tag + '>')

    def handle_data(self, data):
        translated = html.escape(self.translate(data), quote=False) if CJK.search(data) else data
        for original, replacement in [('、', ', '), ('。', '.'), ('／', '/'), ('（', '('), ('）', ')')]:
            translated = translated.replace(original, replacement)
        self.parts.append(translated)

    def handle_entityref(self, name):
        self.parts.append('&' + name + ';')

    def handle_charref(self, name):
        self.parts.append('&#' + name + ';')

    def handle_decl(self, decl):
        self.parts.append('<!' + decl + '>')

    def handle_comment(self, data):
        self.parts.append('<!--' + data + '-->')

def build_english():
    translations = json.loads((ROOT/'scripts/translations.en.json').read_text(encoding='utf-8'))
    for name in PAGES:
        source = (ROOT/name).read_text(encoding='utf-8')
        # Idempotent when called without rebuilding the Chinese pages first.
        source = re.sub(r'<link rel="alternate"[^>]+>', '', source)
        source = re.sub(r'<a class="language-switch"[^>]*>.*?</a>', '', source)
        parser = Translator(translations, name)
        parser.feed(source)
        english = ''.join(parser.parts)
        for filename, text, target, label, lang in [
            (name, source, english_name(name), 'English', 'en'),
            (english_name(name), english, name, '繁體中文', 'zh-Hant'),
        ]:
            switch = f'<a class="language-switch" href="{target}" lang="{lang}" hreflang="{lang}">{label}</a>'
            text = text.replace('</head>', alternates(name) + '</head>')
            text = text.replace('</div></nav>', switch + '</div></nav>')
            (ROOT/filename).write_text(text, encoding='utf-8')
    paths = ['', 'analysis.html', 'resources.html'] + [english_name(name) for name in PAGES]
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += ''.join('  <url><loc>' + SITE + path + '</loc></url>\n' for path in paths)
    (ROOT/'sitemap.xml').write_text(sitemap + '</urlset>\n', encoding='utf-8')
    print('Built three English pages, reciprocal language links and six-page sitemap')

if __name__ == '__main__':
    build_english()
