import json, math, statistics as st, hashlib, html
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/benchmark_metrics.json'
OUT = ROOT / 'data'
raw = json.loads(SOURCE.read_text(encoding='utf-8'))
models = list(raw)
cats = ['counseling', 'agent']
names = dict(zip(models, ['Gemma 4 E4B QAT','Gemma 4 12B QAT','Gemma 4 26B A4B QAT','Gemma 4 31B QAT','Qwen 3.8 27B','Qwen 3.8 Flash Next']))
moe = {models[2], models[5]}
gm = lambda xs: math.exp(st.mean(math.log(x) for x in xs))
pc = lambda x: f'{(x-1)*100:+.2f}%'
cells = {}
rows = []
max_summary_error = 0
for m, model in raw.items():
    for v, variant in model['variants'].items():
        for p, prompt in variant['prompts'].items():
            rr = prompt['runs']
            assert len(rr)==5 and len(set(r['iteration'] for r in rr))==5
            assert all(r['gen_speed_tps']>0 for r in rr)
            cell = dict(model=m, variant=v, prompt=p, category=prompt['category'], n=variant['draft_n'],
                        q='Q8' if '_q8_' in v else ('Q4' if '_q4_' in v else 'none'))
            for field in rr[0]:
                cell[field+'_mean']=st.mean(r[field] for r in rr)
            cell['speed']=cell['gen_speed_tps_mean']
            cell['warm_speed']=st.mean(r['gen_speed_tps'] for r in rr if r['iteration']>1)
            cell['speed_sd']=st.stdev(r['gen_speed_tps'] for r in rr)
            cell['first_prefill_ms']=rr[0]['prefill_time_ms']
            cell['first_cached']=rr[0]['cached_tokens']
            max_summary_error=max(max_summary_error, abs(cell['speed']-prompt['stats']['mean_gen_speed_tps']))
            cells[m,v,p]=cell
            rows.extend(dict(model=m,variant=v,prompt=p,category=prompt['category'],**r) for r in rr)

def prompts(m,c):
    return [p for p,x in raw[m]['variants']['no_mtp']['prompts'].items() if x['category']==c]
def ratio(m,v,c,field='speed',reference='no_mtp'):
    return gm(cells[m,v,p][field]/cells[m,reference,p][field] for p in prompts(m,c))
def balanced(ms,vs,cs=cats,field='speed'):
    return gm(ratio(m,v,c,field) for m in ms for v in vs for c in cs)
q4=[f'mtp_q4_n{n}' for n in range(1,5)]
complete=[m for m in models if 'mtp_q8_n1' in raw[m]['variants']]
result={'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'run_count':len(rows),
        'cell_count':len(cells),'max_summary_error':max_summary_error,
        'main_mtp_q4': balanced(models,q4), 'main_mtp_q4_warm':balanced(models,q4,field='warm_speed')}
result['main_mtp_complete_q4q8']=balanced(complete,q4+[f'mtp_q8_n{n}' for n in range(1,5)])
result['by_model']=[]
for m in models:
    item={'model':names[m],'mtp_q4':balanced([m],q4)}
    if m in complete:
        item['q8_over_q4']=gm(ratio(m,f'mtp_q8_n{n}',c,reference=f'mtp_q4_n{n}') for n in range(1,5) for c in cats)
    result['by_model'].append(item)
result['q8_over_q4']=gm(x['q8_over_q4'] for x in result['by_model'] if 'q8_over_q4' in x)
result['n_effects']=[]
for n in range(1,5):
    v=f'mtp_q4_n{n}'
    item={'n':n,'all':balanced(models,[v]),'counseling':balanced(models,[v],['counseling']),
          'agent':balanced(models,[v],['agent']), 'moe':balanced([m for m in models if m in moe],[v]),
          'dense':balanced([m for m in models if m not in moe],[v])}
    result['n_effects'].append(item)
for x in result['n_effects']:
    base=result['n_effects'][0]
    x['task_interaction_vs_n1']=(x['agent']/base['agent'])/(x['counseling']/base['counseling'])
    x['moe_interaction_vs_n1']=(x['moe']/base['moe'])/(x['dense']/base['dense'])
result['best']=[]
result['model_task_n']=[]
for m in models:
    for c in cats:
        scores={v:ratio(m,v,c) for v in q4}
        scoresall={v:ratio(m,v,c) for v in raw[m]['variants'] if v!='no_mtp'}
        ranked=sorted(scores,key=scores.get,reverse=True)
        bestall=max(scoresall,key=scoresall.get)
        warm=max(q4,key=lambda v:ratio(m,v,c,'warm_speed'))
        result['best'].append(dict(model=names[m],category=c,best_q4=ranked[0],gain=scores[ranked[0]],
                                   runner_gap=scores[ranked[0]]/scores[ranked[1]],best_joint=bestall,
                                   joint_gain=scoresall[bestall],warm_best_q4=warm))
        result['model_task_n'].append(dict(model=names[m],category=c,ratios=[scores[v] for v in q4]))
result['context']=[]
for m in models:
    for p in prompts(m,'counseling'):
        x=cells[m,'no_mtp',p]
        result['context'].append(dict(model=names[m],prompt=p,tokens=x['prompt_tokens_mean'],
                                      speed=x['speed'],prefill_ms=x['first_prefill_ms'],cached=x['first_cached']))
result['threeway_descriptive']=[]
for m in models:
    cc=[ratio(m,v,'counseling') for v in q4];aa=[ratio(m,v,'agent') for v in q4]
    result['threeway_descriptive'].append(dict(model=names[m],interaction_n_vs_1=[(a/aa[0])/(c/cc[0]) for a,c in zip(aa,cc)]))
result['diagnostics']={'first_runs_nonzero_cache':sum(r['iteration']==1 and r['cached_tokens']>0 for r in rows),
 'completion_min':min(r['completion_tokens'] for r in rows),'completion_max':max(r['completion_tokens'] for r in rows),
 'completion_at_4096':sum(r['completion_tokens']==4096 for r in rows),
 'median_cell_cv_percent':st.median(x['speed_sd']/x['speed']*100 for x in cells.values()),
 'max_cell_cv_percent':max(x['speed_sd']/x['speed']*100 for x in cells.values())}
result['secondary']={f:balanced(models,q4,field=f) for f in ['wall_time_s_mean','completion_tokens_mean','draft_acc_percent_mean'] if f!='draft_acc_percent_mean'}
result['acceptance_by_n']=[{'n':n,'mean_percent':st.mean(st.mean(cells[m,f'mtp_q4_n{n}',p]['draft_acc_percent_mean'] for p in prompts(m,c)) for m in models for c in cats)} for n in range(1,5)]
result['n_complete_q_average']=[{'n':n,'gain':balanced(complete,[f'mtp_q4_n{n}',f'mtp_q8_n{n}'])} for n in range(1,5)]
(OUT/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'cell_summaries.json').write_text(json.dumps(list(cells.values()),ensure_ascii=False,indent=2),encoding='utf-8')
