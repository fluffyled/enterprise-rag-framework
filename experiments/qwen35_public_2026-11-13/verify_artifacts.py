from pathlib import Path
import json,hashlib,collections,shutil,datetime,requests
ROOT=Path(__file__).parent
from metrics import ARMS,read

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def main():
 expected=['dataset_manifest.json','baseline_results.json','a1_results.json','a2_results.json','a3_results.json','a4_results.json','metrics_comparison.csv','error_analysis.md','ablation_report.md','training_feasibility.md','final_experiment_report.md','quality_latency.png','source_review.json']
 assert all((ROOT/f).is_file() and (ROOT/f).stat().st_size for f in expected)
 frozen=read(ROOT/'pretest_lock.json');assert all(sha(ROOT/f)==h for f,h in frozen['hashes'].items()),'Original pre-test code/data changed'
 assert sha(ROOT/'baseline.py')==sha(ROOT/'frozen/A0_baseline.py'),'A0 source changed'
 cases=read(ROOT/'test_cases.json');pairs={}
 for a,aid in ARMS.items():
  files=list((ROOT/'runs/test'/aid).glob('*.json'));assert len(files)==40
  rr=[read(p) for p in files];pairs[a]={r['case_id']:r['input_sha256'] for r in rr};assert set(pairs[a])=={c['id'] for c in cases}
  for r in rr:
   for call in r.get('calls',[]):assert call['response']['model'].endswith('Qwen3.5-4B-Q4_K_M.gguf')
 assert all(pairs[a]==pairs['A0'] for a in ARMS),'Paired input mismatch'
 weight=Path(r'D:\хакатон\models\answer-llm\Qwen3.5-4B-Q4_K_M.gguf');actual=sha(weight);assert actual==read(ROOT/'model_manifest.json')['actual_sha256']
 shutil.copyfile(ROOT/'procedure_v3.py',ROOT/'frozen/procedure_v3.py')
 cs={s:{c['id']:c for c in read(ROOT/(s+'_cases.json'))} for s in ['dev','test']}
 joint={s:[{'input_and_gold':cs[s][r['case_id']],'result':r} for r in [read(f) for f in (ROOT/'runs'/s/'A3_v2').glob('*.json')]] for s in cs}
 with (ROOT/'a3_joint_v2_results.json').open('x',encoding='utf8') as f:json.dump(dict(note='Original joint generation, not strict preliminary procedure extraction. Preserved as a separate prototype.',**joint),f,ensure_ascii=False,indent=2)
 s=requests.Session();s.trust_env=False;props=s.get('http://127.0.0.1:8091/props',timeout=10).json();assert props['default_generation_settings']['n_ctx']==4096
 (ROOT/'final_server_props.json').write_text(json.dumps(props,ensure_ascii=False,indent=2),encoding='utf8')
 report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pretest_hashes_unchanged':True,'a0_source_unchanged':True,'all_5_arms_same_40_inputs':True,'only_expected_model_in_saved_successful_responses':True,'model_sha256_after':actual,'model_weights_unchanged':True,'a3_protocol_repair_disclosed':True,'artifacts_exist':expected,'run_counts':{split:{a:len(list((ROOT/'runs'/split/a).glob('*.json'))) for a in [d.name for d in (ROOT/'runs'/split).iterdir() if d.is_dir()]} for split in ['dev','test','confirmation']},'known_limitations':['No independent human semantic ground truth. Same-model judge failed calibration and is diagnostic only.','A3 v3 protocol repair after original test; fresh confirmation has one substantive good and four empty-context OOD guards.','Small short-context public slices, dataset/reference noise, no end-to-end MFTI claim.','One original A0 dev HTTP packet missing; separate replay retained.']}
 (ROOT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 hashes={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name not in ['artifact_hashes.json']}
 (ROOT/'artifact_hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
