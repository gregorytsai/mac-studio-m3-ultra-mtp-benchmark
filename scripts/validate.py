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
  super().__init__(); self.ids=[]; self.geometry=[]; self.canonical=[]; self.alternates={}; self.lang=None; self.text=[]; self.prompt_id=None; self.prompts={}
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if a.get('translate')=='no':
   assert tag=='pre' and a.get('data-prompt-id') in ('prompt_4','prompt_5')
   self.prompt_id=a['data-prompt-id']; self.prompts[self.prompt_id]=''
  if tag=='html':self.lang=a.get('lang')
  if 'id' in a:self.ids.append(a['id'])
  if tag in ['svg','circle','polyline','line']:self.geometry.append((tag,{k:v for k,v in a.items() if k not in ['aria-label']}))
  if tag=='link' and a.get('rel')=='canonical':self.canonical.append(a['href'])
  if tag=='link' and a.get('rel')=='alternate':self.alternates[a['hreflang']]=a['href']
 def handle_endtag(self,tag):
  if tag=='pre':self.prompt_id=None
 def handle_data(self,data):
  if self.prompt_id:self.prompts[self.prompt_id]+=data
  else:self.text.append(data)
agent_prompts=json.loads((ROOT/'data/prompts.agent.json').read_text(encoding='utf-8'))
assert set(agent_prompts)=={'prompt_4','prompt_5'}
assert all(p['category']=='agent' for p in agent_prompts.values())
catalog=json.loads((ROOT/'data/prompt_catalog.json').read_text(encoding='utf-8'))
assert [p['id'] for p in catalog]==[f'prompt_{i}' for i in range(1,6)]
assert all(set(p)=={'id','title','summary','category','disclosure','title_en','summary_en'} for p in catalog)
assert all(p['disclosure']=='summary_only' for p in catalog[:3])
for name in ['index','analysis','resources']:
 zh,en=BilingualPage(),BilingualPage()
 zh.feed((ROOT/(name+'.html')).read_text(encoding='utf-8'))
 en.feed((ROOT/(name+'-en.html')).read_text(encoding='utf-8'))
 assert (zh.lang,en.lang)==('zh-Hant','en')
 assert zh.ids==en.ids and zh.geometry==en.geometry,'Bilingual chart/anchor mismatch'
 assert zh.alternates==en.alternates and set(en.alternates)=={'zh-Hant','en','x-default'}
 assert len(en.canonical)==1 and en.canonical[0]==en.alternates['en']
 assert not re.search(r'[\u3400-\u9fff]',''.join(en.text).replace('繁體中文','')),'Untranslated English content'
 if name=='resources':
  assert zh.prompts==en.prompts=={k:v['content'] for k,v in agent_prompts.items()},'Original prompt content changed in rendering'
assert (ROOT/'sitemap.xml').read_text(encoding='utf-8').count('<loc>')==6
assert not (ROOT/'prompts.json').exists()
assert not (ROOT/'prompts_output').exists()
report={'numeric_runs':count,'schema':'PASS: numeric run fields only; no original prompt titles or content in performance data','public_prompts':'PASS: five task summaries; only prompts 4 and 5 include original content; Chinese and English rendering matches the prompt JSON','python_syntax':'PASS','local_page_links':'PASS','bilingual_pages':'PASS: language, canonical, reciprocal hreflang, chart geometry, anchors and translation completeness outside explicitly labeled original prompts','inference_rerun':False,'scope':'Static validation, not a live model benchmark.'}
(ROOT/'data/validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
# GitHub stores UTF-8/LF text; normalize Windows CRLF before hashing.
files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_text(encoding='utf-8').encode('utf-8')).hexdigest() for p in sorted(ROOT.rglob('*')) if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.name!='manifest.json'}
(ROOT/'data/manifest.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
print(json.dumps(report))
