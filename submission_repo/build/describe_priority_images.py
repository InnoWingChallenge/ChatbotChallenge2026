"""Prepare and validate source-bound equipment/space descriptions with model provenance."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from build.prepare_image_batch import ROOT, RAW, OUT, MANIFEST, Image, ImageOps, read, save, safe_path

DEST = OUT / 'priority_descriptions'
PROMPT_VERSION = 'equipment-space-v1'
API_PROMPT_VERSION = 'equipment-space-api-v3'
SUPPORTED_API_PROMPT_VERSIONS = {'equipment-space-api-v2', API_PROMPT_VERSION}


def validate(record, item):
    for key in ('id', 'sha256'):
        if record.get(key) != item[key]:
            raise ValueError('Source mismatch: ' + key)
    if record.get('viewed') is not True:
        raise ValueError('Missing required visual/model provenance')
    if record.get('model') == 'gpt-6-luna':
        if record.get('reasoning_effort') != 'low' or record.get('prompt_version') != PROMPT_VERSION:
            raise ValueError('Invalid Luna provenance')
    elif record.get('model') == 'gpt-5-mini':
        if (record.get('prompt_version') not in SUPPORTED_API_PROMPT_VERSIONS or record.get('generator') != 'azure_vision_api'
                or record.get('reasoning_effort') not in ('low', 'medium', 'high')
                or len(record.get('prompt_sha256', '')) != 64
                or not record.get('response_model') or record.get('finish_reason') != 'stop'):
            raise ValueError('Invalid API provenance')
        for key in ('location',):
            if not isinstance(record.get(key), str) or not record[key].strip():
                raise ValueError('Missing ' + key)
        for key in ('objects_and_counts', 'colours_and_materials'):
            if not isinstance(record.get(key), list) or not all(isinstance(v, str) and v.strip() for v in record[key]):
                raise ValueError('Invalid ' + key)
    else:
        raise ValueError('Unknown description model')
    if not isinstance(record.get('suitable'), bool):
        raise ValueError('Missing prompt version or suitability')
    if not isinstance(record.get('title'), str) or not record['title'].strip():
        raise ValueError('Missing title')
    for field in ('visible_text', 'visual_facts', 'spatial_relations', 'uncertainties'):
        if not isinstance(record.get(field), list) or not all(isinstance(v, str) and v.strip() for v in record[field]):
            raise ValueError('Invalid ' + field)
    if record['suitable'] and not record['visual_facts']:
        raise ValueError('No visual facts')
    if not record['suitable'] and not record['uncertainties']:
        raise ValueError('Unsuitable image requires a reason')


def prepare():
    retained = read(OUT / 'selection/reviewed_keep.json')
    selected = [r for r in retained if r['reason'] in ('equipment_facility', 'space_layout')]
    manifest = read(MANIFEST)
    previews = RAW / 'priority_description_previews'
    previews.mkdir(parents=True, exist_ok=True)
    tasks = []
    for r in sorted(selected, key=lambda r: (r['reason'], r['id'])):
        raw = safe_path(r['local_path'])
        if hashlib.sha256(raw.read_bytes()).hexdigest() != r['sha256']:
            raise ValueError('Source changed: ' + r['id'])
        preview = previews / (r['sha256'] + '.jpg')
        with Image.open(raw) as src:
            rgba = ImageOps.exif_transpose(src).convert('RGBA')
            rgb = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')
            rgb.thumbnail((1600, 1600))
            rgb.save(preview, quality=92)
        context = []
        for ident in r.get('source_ids', [r['id']]):
            for occurrence in manifest.get(ident, {}).get('occurrences', []):
                if occurrence not in context:
                    context.append(occurrence)
        tasks.append({'id':r['id'], 'sha256':r['sha256'], 'category':r['reason'],
                      'local_path':r['local_path'], 'preview_path':preview.relative_to(ROOT).as_posix(),
                      'url':r['url'], 'source_ids':r.get('source_ids', [r['id']]),
                      'width':r['width'], 'height':r['height'], 'context':context,
                      'prompt_version':PROMPT_VERSION})
    save(DEST / 'tasks.json', tasks)
    equipment = [r for r in tasks if r['category']=='equipment_facility']
    spaces = [r for r in tasks if r['category']=='space_layout']
    pilot = equipment[:3]+spaces[:3]
    save(DEST / 'pilot.json', pilot)
    for i in range(3):
        save(DEST / f'assignment-{i}.json', tasks[i::3])
    print(json.dumps({'images':len(tasks), 'categories':dict(Counter(t['category'] for t in tasks)), 'pilot':len(pilot)}))


def status(dest=DEST):
    tasks = read(dest / 'tasks.json')
    valid, invalid, missing = [], [], []
    for item in tasks:
        try:
            record = read(dest / 'descriptions' / (item['id'] + '.json'))
            if record is None:
                missing.append(item)
                continue
            validate(record, item)
            valid.append(record)
        except ValueError as exc:
            invalid.append({'id':item['id'],'error':str(exc)})
    summary = {'updated_at':datetime.now(timezone.utc).isoformat(), 'selected':len(tasks),
               'described':len(valid), 'suitable':sum(r['suitable'] for r in valid),
               'missing':len(missing), 'invalid':invalid,
               'models':dict(Counter(r['model'] for r in valid)),
               'prompt_versions':dict(Counter(r['prompt_version'] for r in valid)),
               'complete':not missing and not invalid, 'indexed':False}
    save(dest / 'summary.json', summary)
    save(dest / 'remaining.json', missing)
    print(json.dumps(summary))


def export():
    """Publish a validated, complete description manifest; does not mutate databases."""
    tasks=read(DEST/'tasks.json'); entries=[]
    for item in tasks:
        path=DEST/'descriptions'/(item['id']+'.json')
        record=read(path)
        if record is None:
            raise ValueError('Description missing: '+item['id'])
        validate(record,item)
        if hashlib.sha256(safe_path(item['local_path']).read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Raw image changed: '+item['id'])
        entries.append({'id':item['id'],'sha256':item['sha256'],'suitable':record['suitable'],
                        'model':record['model'],'reasoning_effort':record['reasoning_effort'],
                        'prompt_version':record['prompt_version'],'prompt_sha256':record.get('prompt_sha256'),
                        'description_path':path.relative_to(ROOT).as_posix(),
                        'description_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    save(DEST/'release.json',{'schema':2,'models':dict(Counter(e['model'] for e in entries)),
         'released_at':datetime.now(timezone.utc).isoformat(),'entries':entries})
    print(json.dumps({'released':len(entries),'suitable':sum(e['suitable'] for e in entries),'database_modified':False}))


def evidence(repo):
    """Load only released descriptions, retaining visual/context provenance boundaries."""
    from build.ingest_reviewed_images import make_record, sha
    folder=repo/'prompt_from_web/innoacademy/preparation/priority_descriptions'
    release=read(folder/'release.json')
    if release is None:
        return [],{}
    tasks={r['id']:r for r in read(folder/'tasks.json')}
    records,assets=[],{}
    if len({e['id'] for e in release['entries']})!=len(release['entries']):
        raise ValueError('Duplicate release IDs')
    for entry in release['entries']:
        item=tasks[entry['id']]
        path=(repo/entry['description_path']).resolve();path.relative_to(repo.resolve())
        record=read(path);validate(record,item)
        if sha(path.read_bytes())!=entry['description_sha256'] or entry['sha256']!=item['sha256']:
            raise ValueError('Released description changed')
        raw=(repo/item['local_path']).resolve();raw.relative_to(repo.resolve())
        if sha(raw.read_bytes())!=item['sha256']:
            raise ValueError('Released image changed')
        if not record['suitable']:
            continue
        source='webimg_'+item['sha256'][:24]
        assets[source]={'source_id':source,'sha256':item['sha256'],'url':item['url'],
            'raw_path':item['local_path'],'source_type':'web_image','raw_available_at_prepare':True,
            'description_path':entry['description_path'],'description_sha256':entry['description_sha256'],
            'model':record['model'],'reasoning_effort':record['reasoning_effort'],'capture_date':None,
            'prompt_version':record['prompt_version'],'prompt_sha256':record.get('prompt_sha256'),
            'response_model':record.get('response_model'),
            'source_pages':sorted({o.get('source_page','') for o in item['context']}),
            'uncertainties':record['uncertainties']}
        body=' '.join(record['visual_facts']+record['spatial_relations'])
        if record['visible_text']:
            body+=' Legible text: '+ '; '.join(record['visible_text'])+'.'
        meta={'image_type':item['category'],'location':'unknown','status':'model_described',
              'description_model':record['model'],'description_effort':record['reasoning_effort'],
              'prompt_version':record['prompt_version'],'prompt_sha256':record.get('prompt_sha256','not_recorded'),
              'response_model':record.get('response_model',record['model']),
              'description_sha256':entry['description_sha256'],'image_sha256':item['sha256'],
              'uncertainties_json':json.dumps(record['uncertainties'],ensure_ascii=False)}
        records.append(make_record(entry['description_path'],record['title'],'Visible image description',
            body,[source],'image','web_image','visual_description',item['url'],release['released_at'][:10],**meta))
        seen=set()
        for occurrence in item['context']:
            page=occurrence.get('source_page','')
            # Preserve supplied page wording, never infer location from the website host.
            context=' '.join(label+': '+str(occurrence[key]).strip() for key,label in
                [('page_title','Page title'),('caption','Caption'),('alt','Image alternative text')]
                if occurrence.get(key))
            if not page or len(context)<20 or context in seen:
                continue
            seen.add(context)
            records.append(make_record(entry['description_path'],record['title'],'Associated webpage wording',
                context,[source],'text','web_image','web_context',page,release['released_at'][:10],
                image_url=item['url'],**meta))
    return records,assets


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare','status','export'])
    args=parser.parse_args()
    {'prepare':prepare, 'status':status, 'export':export}[args.stage]()
