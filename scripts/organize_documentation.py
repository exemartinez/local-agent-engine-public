"""Organize historical documentation and rebase repository references."""
import json,os,re,shutil
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]; DOC=ROOT/'documentation'
SKIP={'.git','.venv','.idea','__pycache__','runtime','model-downloads','node_modules','run_traceability_backups','doc_organization_backups','.pytest_cache'}
CURRENT={'2026_11_13__19_12_05__final_podium_code_review.md','2026_11_13__12_53_39_441992__all_model_results_with_gemma4.md','2026_11_13__13_58_54__benchmark_run_folder_index.md'}
GUIDES={'hardware_inventory.md','opencode_configuration.md','installation_log.md'}
HISTORY={'feasibility_report.md','final_recommendation.md','progress_log.md','2026_11_05__21_13_33__tested_model_removal.md'}
def target(p):
 n=p.name
 if n=='README.md': return p
 if n in CURRENT: return DOC/'reports'/n
 if n in GUIDES: return DOC/'guides'/n
 if n in HISTORY: return DOC/'archive/project-history'/n
 if 'moe_quantization_queue' in n: return DOC/'archive/queue-snapshots'/n
 if 'seven_model_retry_report' in n: return DOC/'archive/retry-snapshots'/n
 if 'all_model_results_with_gemma4' in n: return DOC/'archive/gemma-attempts'/n
 if 'disk_inventory' in n or 'disk_space_investigation' in n: return DOC/'archive/system-investigations'/n
 return DOC/'archive/benchmark-history'/n

def main():
 mapping={p.resolve():target(p).resolve() for p in DOC.glob('*.md') if p.name!='README.md'}
 if len(set(mapping.values()))!=len(mapping): raise RuntimeError('Duplicate destinations')
 for old,new in mapping.items():
  if old.is_symlink() or old.parent!=DOC.resolve() or not new.is_relative_to(DOC.resolve()) or new.exists(): raise RuntimeError(f'Unsafe move {old} -> {new}')
 candidates=[]
 for base,dirs,names in os.walk(ROOT,followlinks=False):
  dirs[:]=[d for d in dirs if d not in SKIP and not (Path(base)/d).is_symlink()]
  for name in names:
   p=Path(base)/name
   if p.is_symlink() or p.suffix.lower() not in {'.md','.py','.ps1','.json','.jsonl','.csv','.txt','.log','.sh','.toml','.yaml','.yml'}: continue
   try:
    raw=p.read_bytes()
    if b'\0' in raw[:4096]: continue
    text=raw.decode('utf-8-sig'); bom=raw.startswith(b'\xef\xbb\xbf')
   except (OSError,UnicodeDecodeError): continue
   original=text; original_path=p.resolve(); new_path=mapping.get(original_path,original_path)
   if p.suffix.lower()=='.md':
    def replace_link(m):
     u=m.group(1)
     if u.startswith(('http:','https:','mailto:','#','/')) or ' ' in u: return m.group(0)
     path_part,sep,anchor=u.partition('#')
     if not path_part: return m.group(0)
     old_target=(original_path.parent/path_part).resolve(); new_target=mapping.get(old_target,old_target)
     if original_path==new_path and old_target==new_target: return m.group(0)
     relative=os.path.relpath(new_target,new_path.parent).replace('\\\\','/')
     if path_part.endswith('/') and not relative.endswith('/'): relative+='/'
     return ']('+relative+(sep+anchor if sep else '')+')'
    text=re.sub(r'\]\(([^)]+)\)',replace_link,text)
   # Absolute and project-root references in scripts, logs and JSON.
   for old,new in mapping.items():
    old_rel=old.relative_to(ROOT).as_posix();new_rel=new.relative_to(ROOT).as_posix()
    for sep in ('/','\\\\','\\\\\\\\'):
     text=text.replace(old_rel.replace('/',sep),new_rel.replace('/',sep))
   # Exact backticked report filenames in documentation are relative references.
   if p.suffix.lower()=='.md' and original_path.is_relative_to(DOC.resolve()):
    for old,new in mapping.items():
     relative=os.path.relpath(new,new_path.parent).replace('\\\\','/')
     text=text.replace('`'+old.name+'`','`'+relative+'`')
   if text!=original: candidates.append((p,raw,(b'\xef\xbb\xbf' if bom else b'')+text.encode('utf-8')))
 backup=ROOT/'benchmarks/results/doc_organization_backups'/datetime.now().strftime('%Y_%m_%d__%H_%M_%S_%f');backup.mkdir(parents=True)
 manifest={'moves':{str(k.relative_to(ROOT)):str(v.relative_to(ROOT)) for k,v in mapping.items()},'files':[]}
 for i,(p,raw,new) in enumerate(candidates):
  name=f'{i:06d}.bak';(backup/name).write_bytes(raw);manifest['files'].append({'path':str(p.relative_to(ROOT)),'backup':name})
 (backup/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 for p,raw,new in candidates:p.write_bytes(new)
 for old,new in mapping.items():
  new.parent.mkdir(parents=True,exist_ok=True)
  if old.is_symlink() or old.resolve().parent!=DOC.resolve() or not new.resolve().is_relative_to(DOC.resolve()) or new.exists(): raise RuntimeError(f'Unsafe move: {old} -> {new}')
  old.rename(new)
 print(f'Moved {len(mapping)} documents; updated {len(candidates)} referencing files; backup {backup}')
if __name__=='__main__':main()
