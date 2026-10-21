"""Save descriptions authored after direct image inspection; never generate facts."""
import argparse
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'prompt_from_web/innoacademy'

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('batch',type=Path);p.add_argument('descriptions',type=Path)
 a=p.parse_args()
 batch=json.loads(a.batch.read_text(encoding='utf-8'))
 descriptions=json.loads(a.descriptions.read_text(encoding='utf-8'))
 manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
 rp=OUT/'manual_reviews.json'
 reviews=json.loads(rp.read_text(encoding='utf-8')) if rp.exists() else {}
 for number,record in descriptions.items():
  item=batch[int(number)-1]
  assert hashlib.sha256((ROOT/item['local_path']).read_bytes()).hexdigest()==item['sha256']
  assert len(record['paragraphs'])>=2 and all(isinstance(s,str) and s.strip() for s in record['paragraphs'])
  target=OUT/'descriptions'/item['id']/'prompt.md'
  target.parent.mkdir(parents=True,exist_ok=True)
  lines=[f'# {record["title"]}',f'Image ID: {item["id"]}',f'Image source: {item["url"]}',
   'Review method: direct visual inspection by the assistant. Capture date: unknown. Review date: October 13, 2026.',
   '## Visible image description',*record['paragraphs'], '## Webpage context (not visual evidence)']
  occurrences=[]
  for variant in manifest.values():
   if variant.get('sha256')==item['sha256']:
    for occurrence in variant['occurrences']:
     if occurrence not in occurrences:occurrences.append(occurrence)
  for occurrence in occurrences:
   lines.append('Source page: '+occurrence.get('source_page',''))
   for key,label in [('page_title','Page title'),('alt','Alt text'),('caption','Caption'),('nearby_text','Surrounding text')]:
    if occurrence.get(key):lines.append(label+': '+occurrence[key])
  target.write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
  reviews[item['sha256']]={'image_id':item['id'],'description_path':target.relative_to(ROOT).as_posix(),
   'status':'completed','review_method':'assistant_direct_visual_inspection','reviewed_at':datetime.now(timezone.utc).isoformat(),
   'type':record.get('type','unknown'),'location':record.get('location','unknown')}
 temp=rp.with_suffix('.json.tmp');temp.write_text(json.dumps(reviews,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(rp)
 print(f'Saved {len(descriptions)} directly inspected image descriptions; total unique reviewed images: {len(reviews)}')

if __name__=='__main__':main()
