"""Discover, download and describe Academy website images without rebuilding Chroma."""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import threading
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'submission_repo'))
from build import scrape

SITE = 'https://innoacademy.engg.hku.hk/'
HOST = urlparse(SITE).netloc
OUTPUT = ROOT / 'prompt_from_web' / 'innoacademy'
RAW = ROOT / 'submission_repo/data/web_academy'
PROMPT = ROOT / 'prompt_from_web/DESCRIPTION_PROMPT.txt'
TLS = threading.local()

def now():
    return datetime.now(timezone.utc).isoformat()

def read(name, default):
    p = OUTPUT / name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

def save(name, value):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    p = OUTPUT / name
    temporary = p.with_suffix(p.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(p)

def session():
    if not hasattr(TLS, 'session'):
        TLS.session = scrape.build_session()
    return TLS.session

def get(url):
    r = session().get(url, timeout=(15, 60))
    r.raise_for_status()
    return r

def fail(stage, url, exc):
    # Never serialize request headers, credentials or SDK exception bodies.
    response = getattr(exc, 'response', None)
    return {'stage':stage, 'url':url, 'error_type':type(exc).__name__,
            'http_status':getattr(exc, 'status_code', None) or getattr(response, 'status_code', None), 'attempted_at':now()}

def discover(workers):
    failures = read('failures.json', {})
    robots = RobotFileParser(urljoin(SITE, 'robots.txt'))
    try:
        robots.parse(get(robots.url).text.splitlines())
    except requests.HTTPError as exc:
        if exc.response.status_code != 404:
            raise
        robots.parse([])
    urls = sorted(set(scrape._sitemap_urls(SITE) + [SITE]))
    urls = [u for u in urls if scrape.is_allowed_url(u, SITE) and robots.can_fetch(scrape.USER_AGENT,u)]
    save('discovered_pages.json', urls)
    pages = read('pages.json', {})
    records = read('manifest.json', {})
    def add(src, occurrence):
        if not src or not src.startswith(('https://','http://')):
            return
        ident = hashlib.sha256(src.encode()).hexdigest()[:24]
        item = records.setdefault(ident, {'id':ident,'url':src,'occurrences':[], 'download_status':'pending','description_status':'pending'})
        if occurrence not in item['occurrences']:
            item['occurrences'].append(occurrence)
    def fetch_page(url):
        response = get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        page = scrape.extract(response.text,url,now())
        extra = []
        for image in soup.select('img'):
            src = scrape._image_source(image,url)
            parent = image.find_parent(['figure','p','section','div'])
            extra.append({'src':src,'alt':image.get('alt',''), 'caption':'',
                          'nearby_text': parent.get_text(' ',strip=True)[:2000] if parent else ''})
        for node in soup.select('[style]'):
            for match in re.findall(r'url\([\"\x27]?([^\)\"\x27]+)',node.get('style','')):
                if not match.startswith('data:'):
                    extra.append({'src':urljoin(url,match),'alt':'','caption':'','nearby_text':node.get_text(' ',strip=True)[:2000]})
        for meta in soup.select('meta[property="og:image"], meta[name="twitter:image"]'):
            extra.append({'src':urljoin(url,meta.get('content','')),'alt':'','caption':'','nearby_text':''})
        directory = RAW / 'pages'
        directory.mkdir(parents=True, exist_ok=True)
        with gzip.open(directory / (hashlib.sha256(url.encode()).hexdigest()[:24]+'.html.gz'),'wt',encoding='utf-8') as f:
            f.write(response.text)
        page['extra_images'] = extra
        return page
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(fetch_page,u):u for u in urls if u not in pages}
        for i,future in enumerate(as_completed(tasks),1):
            u=tasks[future]
            try:
                pages[u]=future.result()
                failures.pop('page:'+u,None)
            except Exception as exc:
                failures['page:'+u]=fail('page',u,exc)
            if i%25==0:
                save('pages.json',pages);save('failures.json',failures)
                print(f'pages completed {len(pages)}/{len(urls)}',flush=True)
    save('pages.json',pages)
    for u,page in pages.items():
        for image in page.get('images',[])+page.get('extra_images',[]):
            add(image.get('src',''),{'source_page':u,'page_title':page.get('title',''),
                'alt':image.get('alt',''),'caption':image.get('caption',''),
                'nearby_text':image.get('nearby_text',''),'retrieved_at':page.get('retrieved_at'), 'discovery':'page_reference'})
    media_url=urljoin(SITE,'wp-json/wp/v2/media')
    if not robots.can_fetch(scrape.USER_AGENT,media_url):
        print('Public media enumeration excluded by robots; using page references.',flush=True)
    else:
        first=get(media_url+'?per_page=100&page=1')
        count=int(first.headers.get('X-WP-TotalPages','1'))
        batches={1:first.json()}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            tasks={pool.submit(get,media_url+f'?per_page=100&page={n}'):n for n in range(2,count+1)}
            for future in as_completed(tasks):
                n=tasks[future]
                try:
                    batches[n]=future.result().json()
                    failures.pop('media:'+str(n),None)
                except Exception as exc:
                    failures['media:'+str(n)]=fail('media',media_url+f'?page={n}',exc)
        save('media.json',batches)
        for batch in batches.values():
            for media in batch:
                if not media.get('mime_type','').startswith('image/'):
                    continue
                text=lambda field:BeautifulSoup(media.get(field,{}).get('rendered',''),'html.parser').get_text(' ',strip=True)
                add(media.get('source_url',''),{'source_page':media.get('link',''),'page_title':text('title'),
                    'alt':media.get('alt_text',''),'caption':text('caption'),'nearby_text':text('description'),
                    'media_id':media['id'],'parent_post_id':media.get('post'), 'published_at':media.get('date_gmt'),
                    'retrieved_at':now(),'discovery':'public_media'})
    save('manifest.json',records);save('failures.json',failures)
    report()

def download(workers,limit):
    records=read('manifest.json',{})
    failures=read('failures.json',{})
    RAW.mkdir(parents=True,exist_ok=True)
    robots=RobotFileParser(urljoin(SITE,'robots.txt'))
    robots.parse(get(robots.url).text.splitlines())
    def one(item):
        u=item['url']
        # The requested collection is restricted to images hosted by the first website.
        if urlparse(u).netloc.lower()!=HOST:
            return {'download_status':'external_reference','description_status':'not_requested_external'}
        if not robots.can_fetch(scrape.USER_AGENT,u):
            return {'download_status':'robots_excluded','description_status':'not_processed'}
        response=get(u)
        mime=response.headers.get('Content-Type','').partition(';')[0].lower()
        data=response.content
        if not mime.startswith('image/'):
            raise ValueError('Not an image response')
        digest=hashlib.sha256(data).hexdigest()
        extension={ 'image/jpeg':'.jpg','image/png':'.png','image/gif':'.gif','image/webp':'.webp',
                    'image/svg+xml':'.svg','image/tiff':'.tiff','image/avif':'.avif'}.get(mime,'.img')
        p=RAW/'images'/(item['id']+extension)
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(data)
        info={'download_status':'downloaded','local_path':p.relative_to(ROOT).as_posix(),'sha256':digest,
              'content_type':mime,'bytes':len(data),'retrieved_at':now()}
        try:
            with Image.open(io.BytesIO(data)) as im:
                info.update(width=im.width,height=im.height,frames=getattr(im,'n_frames',1))
        except Exception:
            info['description_status']='unsupported_format'
        return info
    pending=[v for v in records.values() if v.get('download_status') in {'pending','failed'}]
    if limit is not None:pending=pending[:limit]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(one,v):v['id'] for v in pending}
        for i,future in enumerate(as_completed(tasks),1):
            ident=tasks[future]
            try:
                records[ident].update(future.result());failures.pop('download:'+ident,None)
            except Exception as exc:
                records[ident]['download_status']='failed'
                failures['download:'+ident]=fail('download',records[ident]['url'],exc)
            if i%25==0:
                save('manifest.json',records);save('failures.json',failures)
                print(f'download processed {i}/{len(pending)}',flush=True)
    canonical={}
    for ident,item in sorted(records.items()):
        if item.get('sha256'):
            main=canonical.setdefault(item['sha256'],ident)
            item['canonical_id']=main
    save('manifest.json',records);save('failures.json',failures)
    report()

def describe(limit):
    from dotenv import load_dotenv
    load_dotenv(ROOT/'submission_repo/.env')
    from bot import llm
    records=read('manifest.json',{})
    failures=read('failures.json',{})
    prompt=PROMPT.read_text(encoding='utf-8')
    pending=[v for v in records.values() if v.get('download_status')=='downloaded' and
             v.get('canonical_id',v['id'])==v['id'] and v.get('description_status') not in {'completed','unsupported_format'}]
    if limit is not None:pending=pending[:limit]
    for i,item in enumerate(pending,1):
        try:
            path=ROOT/item['local_path']
            with Image.open(path) as im:
                im.seek(0)
                pixels=ImageOps.exif_transpose(im).convert('RGB')
                pixels.thumbnail((2400,2400))
                data=io.BytesIO();pixels.save(data,format='JPEG',quality=95)
            result=llm._client(llm.VISION_URL).chat.completions.create(
                model=llm.VISION_DEPLOYMENT,max_tokens=6000,
                messages=[{'role':'user','content':[{'type':'text','text':prompt},
                  {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(data.getvalue()).decode(),'detail':'high'}}]}])
            choice=result.choices[0]
            description=(choice.message.content or '').strip()
            if not description or choice.finish_reason=='length':
                raise ValueError('Empty or truncated description; not saved as completed')
            p=OUTPUT/'descriptions'/item['id']/'prompt.md'
            p.parent.mkdir(parents=True,exist_ok=True)
            variants=[v for v in records.values() if v.get('canonical_id',v['id'])==item['id']]
            occurrences=[]
            for variant in variants:
                for occurrence in variant['occurrences']:
                    if occurrence not in occurrences:occurrences.append(occurrence)
            text=f'# Website image {item["id"]}\n\nImage source: {item["url"]}\n\n'
            text+='## Visible image description\n\n'+description+'\n\n## Webpage context (not visual evidence)\n\n'
            if item.get('frames',1)>1:text+='Only the first frame of the animated image was described.\n\n'
            for occurrence in occurrences:
                text+='Source page: '+occurrence.get('source_page','')+'\n\n'
                for key,label in [('page_title','Page title'),('alt','Alt text'),('caption','Caption'),('nearby_text','Surrounding text')]:
                    if occurrence.get(key):text+=label+': '+occurrence[key]+'\n\n'
            p.write_text(text,encoding='utf-8')
            item.update(description_status='completed',description_path=p.relative_to(ROOT).as_posix(),
                        described_at=now(),model=llm.VISION_DEPLOYMENT,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                        input_resolution=[pixels.width,pixels.height],review_status='needs_sample_review')
            for variant in variants:
                if variant['id']!=item['id']:
                    variant.update(description_status='duplicate',description_path=item['description_path'])
            failures.pop('describe:'+item['id'],None)
            print(f'described {i}/{len(pending)}: {item["id"]}',flush=True)
        except Exception as exc:
            failures['describe:'+item['id']]=fail('describe',item['url'],exc)
            item['description_status']='failed'
            save('manifest.json',records);save('failures.json',failures);report()
            status=getattr(exc,'status_code',None)
            # A shared gateway failure must not generate thousands of failing requests.
            if status in {400,401,403,404,429} or type(exc).__name__ in {'APIConnectionError','APITimeoutError','RuntimeError'}:
                print(f'Vision unavailable: {type(exc).__name__}, HTTP {status}. Progress saved.',flush=True)
                return
        save('manifest.json',records);save('failures.json',failures)
    report()

def report():
    from collections import Counter
    records=read('manifest.json',{})
    reviews=read('manual_reviews.json',{})
    effective=Counter()
    for item in records.values():
        review=reviews.get(item.get('sha256',''))
        effective['completed_direct_review' if review and (ROOT/review['description_path']).exists() else item.get('description_status','pending')]+=1
    status={'updated_at':now(),'site':SITE,'discovered_pages':len(read('discovered_pages.json',[])),
       'fetched_pages':len(read('pages.json',{})),'image_urls':len(records),
       'download_status':dict(Counter(v.get('download_status','pending') for v in records.values())),
       'description_status':dict(effective),
       'directly_reviewed_unique_images':len(reviews),
       'unique_downloaded_content':len({v['sha256'] for v in records.values() if v.get('sha256')}),
       'failure_count':len(read('failures.json',{}))}
    save('status.json',status)
    print(json.dumps(status,ensure_ascii=True),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['discover','download','describe','report'])
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--limit',type=int)
    a=p.parse_args()
    if a.workers<1 or a.workers>8:p.error('workers must be between 1 and 8')
    if a.stage=='discover':discover(a.workers)
    elif a.stage=='download':download(a.workers,a.limit)
    elif a.stage=='describe':describe(a.limit)
    else:report()

if __name__=='__main__':main()
