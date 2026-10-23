"""Validate public schema, recomputed counts, links and source syntax."""
import ast, json, math, hashlib, re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
ROOT=Path(__file__).resolve().parents[1]
raw=json.loads((ROOT/'data/benchmark_metrics.json').read_text(encoding='utf-8'))
count=0
allowed={'iteration','wall_time_s','prompt_tokens','cached_tokens','completion_tokens','prefill_speed_tps','prefill_time_ms','gen_speed_tps','gen_time_ms','draft_n','draft_n_accepted','draft_acc_percent'}
for model in raw.values():
 assert set(model)=={'id','display_name','variants'}
 for variant in model['variants'].values():
  assert set(variant)=={'config_name','spec_type','draft_quant','draft_n','load_time_s','prompts'}
  for p in variant['prompts'].values():
   assert set(p)=={'category','stats','runs'}
   assert set(p['stats'])=={'mean_gen_speed_tps'}
   assert len(p['runs'])==5
   for r in p['runs']:
    assert set(r)==allowed
    assert all(type(v) in [int,float] and math.isfinite(v) for v in r.values())
    count+=1
assert count==1250
for p in (ROOT/'scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
class Links(HTMLParser):
 def handle_starttag(self,tag,attrs):
  for key,value in attrs:
   if key in ['href','src'] and value and not urlsplit(value).scheme and not value.startswith('#'):
    path=unquote(urlsplit(value).path)
    assert (ROOT/path).exists(),path
for p in ROOT.glob('*.html'):Links().feed(p.read_text(encoding='utf-8'))
class BilingualPage(HTMLParser):
 def __init__(self):
  super().__init__(); self.ids=[]; self.geometry=[]; self.canonical=[]; self.alternates={}; self.lang=None; self.text=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='html':self.lang=a.get('lang')
  if 'id' in a:self.ids.append(a['id'])
  if tag in ['svg','circle','polyline','line']:self.geometry.append((tag,{k:v for k,v in a.items() if k not in ['aria-label']}))
  if tag=='link' and a.get('rel')=='canonical':self.canonical.append(a['href'])
  if tag=='link' and a.get('rel')=='alternate':self.alternates[a['hreflang']]=a['href']
 def handle_data(self,data):self.text.append(data)
for name in ['index','analysis','resources']:
 zh,en=BilingualPage(),BilingualPage()
 zh.feed((ROOT/(name+'.html')).read_text(encoding='utf-8'))
 en.feed((ROOT/(name+'-en.html')).read_text(encoding='utf-8'))
 assert (zh.lang,en.lang)==('zh-Hant','en')
 assert zh.ids==en.ids and zh.geometry==en.geometry,'Bilingual chart/anchor mismatch'
 assert zh.alternates==en.alternates and set(en.alternates)=={'zh-Hant','en','x-default'}
 assert len(en.canonical)==1 and en.canonical[0]==en.alternates['en']
 assert not re.search(r'[\u3400-\u9fff]',''.join(en.text).replace('繁體中文','')),'Untranslated English content'
assert (ROOT/'sitemap.xml').read_text(encoding='utf-8').count('<loc>')==6
assert not (ROOT/'prompts.json').exists()
assert not (ROOT/'prompts_output').exists()
report={'numeric_runs':count,'schema':'PASS: numeric run fields only; no original prompt titles or content','python_syntax':'PASS','local_page_links':'PASS','bilingual_pages':'PASS: language, canonical, reciprocal hreflang, chart geometry, anchors and translation completeness','inference_rerun':False,'scope':'Static validation, not a live model benchmark.'}
(ROOT/'data/validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# GitHub stores UTF-8/LF text; normalize Windows CRLF before hashing.
files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_text(encoding='utf-8').encode('utf-8')).hexdigest() for p in sorted(ROOT.rglob('*')) if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.name!='manifest.json'}
(ROOT/'data/manifest.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
print(json.dumps(report))
