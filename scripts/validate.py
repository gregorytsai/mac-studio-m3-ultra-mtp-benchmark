"""Validate public schema, recomputed counts, links and source syntax."""
import ast, json, math, hashlib
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
    path=unquote(value.split('#')[0])
    assert (ROOT/path).exists(),path
for p in ROOT.glob('*.html'):Links().feed(p.read_text(encoding='utf-8'))
assert not (ROOT/'prompts.json').exists()
assert not (ROOT/'prompts_output').exists()
report={'numeric_runs':count,'schema':'PASS: numeric run fields only; no original prompt titles or content','python_syntax':'PASS','local_page_links':'PASS','inference_rerun':False,'scope':'Static validation, not a live model benchmark.'}
(ROOT/'data/validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*')) if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.name!='manifest.json'}
(ROOT/'data/manifest.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
print(json.dumps(report))
