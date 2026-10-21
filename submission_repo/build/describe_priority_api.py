"""Resume remaining priority-image descriptions through the configured GPT-5-mini gateway.

python -m build.describe_priority_api plan
python -m build.describe_priority_api run --limit 3
python -m build.describe_priority_api run
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import time

from build import describe_priority_images as batch

PROMPT_FILE = batch.ROOT / 'prompt_from_web/DESCRIPTION_PROMPT.txt'
FORMAT_PROMPT = '''

EQUIPMENT / FACILITY / SPACE EVIDENCE PRIORITIES:
Apply the five fields above with these task-specific rules:
- Inspect equipment nameplates, control columns, room signs and posted instructions before
  incidental scene details. Prioritize exact equipment names, brands, model numbers, use/type
  labels, room identifiers and operating/safety headings. Do not omit a legible small label
  merely because a larger brand logo has already been transcribed.
- Make a second visual pass over each equipment panel and sign for missed text before
  returning the answer. Transcribe only what is actually readable; never complete a model
  number or instruction from prior knowledge. Preserve all other legible text as required above.
- For partially legible labels, preserve readable fragments in visible_text with [unreadable]
  in place of the missing fragment. Identify the label's position in uncertainties so a later
  crop can target it. Avoid standalone, repeated [unreadable] entries with no identifiable label.
- Exact counts require individually distinguishable objects. With overlap, cropping or
  occlusion, use an explicitly bounded visible minimum only if it is demonstrable; otherwise
  say the count cannot be determined. Do not give an exact count and then retract it as
  approximate in uncertainties. Distinguish a complete assembly from its parts: pop filters,
  stands and earcups do not by themselves establish microphone or headphone totals.
- Prioritize equipment, fixed facilities, work surfaces, circulation and spatial relationships
  in objects_and_counts and spatial_relations. Mention people briefly where relevant to room
  use; omit incidental cups, clothing, bags, boxes and transient clutter unless they explain
  access, an obstruction or an equipment relationship. Do not spend effort counting crowds
  or obscured stools. A photographed count never establishes total room inventory or capacity.
- Describe visible appearance without assigning an unsupported device type, material,
  operating state or light source. Put unresolved identifications in uncertainties; do not
  turn them into confident facts in title or objects_and_counts.
- Keep statements concise and non-redundant. Report uncertainty for the specific observation
  concerned, not generic disclaimers. If no room identifier is visible, location must be
  "unknown from image"; do not invent an association with a named facility.
- Treat readable equipment labels as transcribed evidence, not proof of specifications.
  If labels conflict, retain both and state the conflict rather than choosing an interpretation.
These rules refine the evidence priorities; they do not authorize guessing missing details.

OUTPUT FORMAT ADAPTER (replaces only the paragraph/plain-text output instruction above):
Return one JSON object, not markdown, using these fields:
title: concise English title grounded in the image;
suitable: boolean, whether this image contains useful equipment/facility/layout evidence;
location: exact visible location name/number, or "unknown from image";
objects_and_counts: array of factual English sentences covering objects and reliable counts;
visible_text: array of exact transcriptions of ALL legible text, preserving its original language;
spatial_relations: array of English sentences about layout and relationships;
colours_and_materials: array of English sentences about distinctive visible colours/materials;
uncertainties: array of English sentences on unreadable text, ambiguity, cropping or limits.
Use all fields; use [] when nothing is visible in a category. Do not limit coverage to a fixed
number of facts. A suitable:false result must include its reason in uncertainties.
Keep all five evidence requirements above. Do not infer that every scene is in Innovation Wing.
No webpage context or filename should be treated as visual evidence. Do not output IDs, hashes,
model names or technical metadata: the program adds those from the actual request and source.
'''


class ModelIdentityError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def run_lock(dest):
    dest.mkdir(parents=True, exist_ok=True)
    # Lock lives in ignored raw data; the operating system releases it on exit/crash.
    lock_path=batch.RAW/'priority_api.lock';lock_path.parent.mkdir(parents=True,exist_ok=True)
    with lock_path.open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1): handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            try: msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as exc: raise RuntimeError('Another priority API job is running') from exc
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try: yield
        finally:
            handle.seek(0)
            if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def plan(dest=batch.DEST, root=batch.ROOT):
    tasks=batch.read(dest/'tasks.json')
    if not tasks: raise ValueError('Missing tasks.json; prepare the priority batch first')
    if len({t['id'] for t in tasks})!=len(tasks): raise ValueError('Duplicate task IDs')
    keep={r['id']:r for r in batch.read(dest.parent/'selection/reviewed_keep.json', [])}
    if not keep: raise ValueError('Missing reviewed_keep.json; refusing an unapproved image list')
    queued,blocked,excluded,completed,registry=[],[],[],[],[]
    for item in tasks:
        ident=item['id']
        if (ident not in keep or keep[ident]['sha256']!=item['sha256']
                or item.get('category') not in ('equipment_facility','space_layout')):
            excluded.append(ident)
            registry.append({'id':ident,'sha256':item['sha256'],'state':'excluded','model':'',
                'response_model':'','reasoning_effort':'','prompt_version':'','suitable':'','description_path':''})
            continue
        try:
            raw=(root/item['local_path']).resolve();raw.relative_to(root.resolve())
            if hashlib.sha256(raw.read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('raw_hash_mismatch')
            output=dest/'descriptions'/(ident+'.json')
            record=batch.read(output)
            if record is not None:
                batch.validate(record,item)
                completed.append(record)
                registry.append({'id':ident,'sha256':item['sha256'],'state':'completed',
                    'model':record['model'],'response_model':record.get('response_model',''),
                    'reasoning_effort':record['reasoning_effort'],'prompt_version':record['prompt_version'],
                    'suitable':record['suitable'],'description_path':output.relative_to(root).as_posix()})
            elif output.exists():
                raise ValueError('existing_output_is_null')
            else:
                queued.append(item)
                registry.append({'id':ident,'sha256':item['sha256'],'state':'pending','model':'',
                    'response_model':'','reasoning_effort':'','prompt_version':'','suitable':'','description_path':''})
        except (ValueError, OSError, TypeError, KeyError) as exc:
            blocked.append({'id':ident,'error_type':type(exc).__name__, 'reason':'source_or_existing_description_invalid'})
            registry.append({'id':ident,'sha256':item['sha256'],'state':'blocked','model':'',
                'response_model':'','reasoning_effort':'','prompt_version':'','suitable':'','description_path':''})
    summary={'planned_at':now(),'total':len(tasks),'cached_skip':len(completed),
             'by_model':dict(Counter(r['model'] for r in completed)), 'queued':len(queued),
             'blocked':len(blocked),'excluded':len(excluded),'network_requests_made':0}
    batch.save(dest/'api_plan.json',{'summary':summary,'queued_ids':[t['id'] for t in queued],
                                   'blocked':blocked,'excluded_ids':excluded})
    registry_path=dest/'description_registry.csv'
    temp=registry_path.with_suffix('.csv.tmp')
    with temp.open('w',encoding='utf-8-sig',newline='') as handle:
        fields=['id','sha256','state','model','response_model','reasoning_effort','prompt_version','suitable','description_path']
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(registry)
    temp.replace(registry_path)
    return queued,summary


def image_data(item, root, max_edge):
    path=(root/item['local_path']).resolve();path.relative_to(root.resolve())
    if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']: raise ValueError('Raw image changed')
    with batch.Image.open(path) as source:
        if getattr(source,'n_frames',1)!=1: raise ValueError('Animated images need separate handling')
        rgba=batch.ImageOps.exif_transpose(source).convert('RGBA')
        image=batch.Image.alpha_composite(batch.Image.new('RGBA',rgba.size,'white'),rgba).convert('RGB')
        image.thumbnail((max_edge,max_edge))
        buffer=io.BytesIO();image.save(buffer,format='JPEG',quality=95)
        encoded=buffer.getvalue()
        return encoded,[image.width,image.height]


def describe(item, client, deployment, prompt, max_edge=2400, max_tokens=6000, effort='low', root=batch.ROOT):
    data,size=image_data(item,root,max_edge)
    response=client.chat.completions.create(model=deployment,reasoning_effort=effort,
        max_completion_tokens=max_tokens,response_format={'type':'json_object'},
        messages=[{'role':'user','content':[{'type':'text','text':prompt},
            {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(data).decode(), 'detail':'high'}}]}])
    if not response.choices: raise ValueError('No completion choice')
    returned_model=getattr(response,'model',None)
    if not isinstance(returned_model,str) or not returned_model.startswith('gpt-5-mini'):
        raise ModelIdentityError('Gateway did not identify the response as GPT-5-mini; refusing misleading model label')
    choice=response.choices[0]
    if choice.finish_reason!='stop' or getattr(choice.message,'refusal',None):
        raise ValueError('Refused, incomplete or truncated response; not completed')
    content=choice.message.content or ''
    payload=json.loads(content)
    if not isinstance(payload,dict):raise ValueError('Expected a JSON object')
    required=['title','suitable','location','objects_and_counts','visible_text','spatial_relations','colours_and_materials','uncertainties']
    if any(k not in payload for k in required):raise ValueError('Missing structured description fields')
    record={k:payload[k] for k in required}
    # Validate types before concatenation; metadata is always from code, never model-authored.
    for key in required[3:]:
        if not isinstance(record[key],list) or not all(isinstance(v,str) and v.strip() for v in record[key]):
            raise ValueError('Invalid list: '+key)
    if not isinstance(record['location'],str) or not record['location'].strip():raise ValueError('Invalid location')
    record['visual_facts']=record['objects_and_counts']+record['colours_and_materials']
    if record['location'].strip().lower()!='unknown from image':
        record['visual_facts']=['Visible location text: '+record['location']]+record['visual_facts']
    if record['suitable'] and not record['visual_facts'] and record['visible_text']:
        record['visual_facts']=['The image contains legible text recorded in visible_text.']
    usage=getattr(response,'usage',None)
    record.update(id=item['id'],sha256=item['sha256'],model=deployment,
        response_model=returned_model,generator='azure_vision_api',
        reasoning_effort=effort,prompt_version=batch.API_PROMPT_VERSION,
        prompt_sha256=hashlib.sha256(prompt.encode('utf-8')).hexdigest(),viewed=True,
        described_at=now(),input_resolution=size,input_sha256=hashlib.sha256(data).hexdigest(),
        image_detail='high',finish_reason=choice.finish_reason,response_id=getattr(response,'id',None),
        usage=usage.model_dump() if usage else None,max_completion_tokens=max_tokens,
        review_status='needs_sample_review')
    batch.validate(record,item)
    return record


def run(args, dest=batch.DEST, root=batch.ROOT, sleep=time.sleep):
    queued,summary=plan(dest,root)
    print(json.dumps(summary),flush=True)
    if args.limit is not None:queued=queued[:args.limit]
    if not queued:return 1 if summary['blocked'] else 0
    # No network/client/env dependency for plan or fully cached runs.
    from dotenv import load_dotenv
    load_dotenv(root/'submission_repo/.env')
    from bot import llm
    if llm.VISION_DEPLOYMENT!='gpt-5-mini':
        raise ValueError('Set VISION_DEPLOYMENT=gpt-5-mini in this worktree .env (or environment); refusing a different model')
    client=llm._client(llm.VISION_URL).with_options(timeout=args.timeout,max_retries=0)
    base_prompt=PROMPT_FILE.read_text(encoding='utf-8')
    prompt=base_prompt.rstrip()+FORMAT_PROMPT
    prompt_hash=hashlib.sha256(prompt.encode('utf-8')).hexdigest()
    snapshot=dest/'prompts'/(prompt_hash+'.txt');snapshot.parent.mkdir(parents=True,exist_ok=True)
    snapshot.write_text(prompt,encoding='utf-8')
    errors=batch.read(dest/'api_failures.json',{})
    failed=0;consecutive_failures=0
    try:
        for number,item in enumerate(queued,1):
            output=dest/'descriptions'/(item['id']+'.json')
            if output.exists():
                print('SKIP appeared since plan: '+item['id'],flush=True);continue
            print(f'[{number}/{len(queued)}] {item["id"]} -> {llm.VISION_DEPLOYMENT}',flush=True)
            for attempt in range(args.retries+1):
                try:
                    record=describe(item,client,llm.VISION_DEPLOYMENT,prompt,args.max_edge,args.max_completion_tokens,args.reasoning_effort,root)
                    record['base_prompt_sha256']=hashlib.sha256(base_prompt.encode('utf-8')).hexdigest()
                    record['prompt_path']=snapshot.relative_to(root).as_posix()
                    if output.exists():raise FileExistsError('Description appeared; refusing overwrite')
                    batch.save(output,record)
                    errors.pop(item['id'],None);batch.save(dest/'api_failures.json',errors)
                    consecutive_failures=0
                    print('SAVED '+item['id'],flush=True)
                    break
                except Exception as exc:
                    status=getattr(exc,'status_code',None)
                    errors[item['id']]={'id':item['id'],'model':llm.VISION_DEPLOYMENT,'failed_at':now(),
                        'error_type':type(exc).__name__,'http_status':status,'attempt':attempt+1}
                    batch.save(dest/'api_failures.json',errors)
                    print(f'FAILED {item["id"]}: {type(exc).__name__}, HTTP {status}',flush=True)
                    if isinstance(exc,ModelIdentityError):
                        print('Unexpected response model. Stopping without mislabelling results.',flush=True)
                        return 1
                    if status in (400,401,403,404):
                        print({400:'Request rejected; check gateway model/parameter support.',401:'Check API key/.env.',
                               403:'Gateway denied access. Connect HKU VPN and retry.',404:'Check deployment and gateway route.'}[status],flush=True)
                        return 1
                    transient=status in (408,429,500,502,503,504) or type(exc).__name__ in ('APITimeoutError','APIConnectionError')
                    if transient and attempt<args.retries:
                        sleep(min(30,2**(attempt+1)));continue
                    failed+=1;consecutive_failures+=1
                    if consecutive_failures>=3:
                        print('Three consecutive image failures; stopping. Inspect failures before resuming.',flush=True)
                        return 1
                    break
    finally:
        _,current=plan(dest,root)
        print(json.dumps(current),flush=True)
        batch.status(dest)
    return 1 if failed or summary['blocked'] else 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['plan','run'])
    parser.add_argument('--limit',type=int)
    parser.add_argument('--max-edge',type=int,default=2400)
    parser.add_argument('--max-completion-tokens',type=int,default=6000)
    parser.add_argument('--reasoning-effort',choices=['low','medium','high'],default='low')
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--retries',type=int,default=2)
    args=parser.parse_args()
    if (args.limit is not None and args.limit<1) or args.max_edge<256 or args.max_completion_tokens<512 or args.timeout<=0 or args.retries<0:
        parser.error('Positive limit/timeout, max-edge>=256, max-completion-tokens>=512, retries>=0 required')
    with run_lock(batch.DEST):
        if args.stage=='plan':
            _,summary=plan();print(json.dumps(summary,indent=2))
        else:
            try:raise SystemExit(run(args))
            except KeyboardInterrupt:
                print('Interrupted. Saved images will be skipped on the next run.');raise SystemExit(130)
            except (ValueError,RuntimeError) as exc:
                print(str(exc));raise SystemExit(1)


if __name__=='__main__':main()
