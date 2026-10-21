"""Build a portable image review page and apply exported human decisions locally."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote, urlparse
from build.prepare_image_batch import ROOT, OUT, read, save

DEST = OUT / 'selection'
TEMPLATE = Path(__file__).with_name('image_review.html')


def validate_reviews(payload, rows):
    if payload.get('schema') != 'innowing-image-review-v1' or not isinstance(payload.get('records'), list):
        raise ValueError('Not an InnoWing image review export')
    by_id = {r['id']: r for r in rows}
    result = {}
    for entry in payload['records']:
        ident = entry.get('id')
        if ident not in by_id or entry.get('sha256') != by_id[ident]['sha256']:
            raise ValueError(f'Unknown image or changed hash: {ident}')
        if ident in result or entry.get('decision') not in ('keep', 'defer', 'review'):
            raise ValueError(f'Duplicate or invalid decision: {ident}')
        if not isinstance(entry.get('note', ''), str) or len(entry.get('note', '')) > 2000:
            raise ValueError('Review note must be text of at most 2000 characters')
        result[ident] = {k: entry.get(k, '') for k in ('id', 'sha256', 'decision', 'note', 'updated_at')}
    return result


def render_review(rows, dest=DEST, root=ROOT):
    aliases = {alias: r['id'] for r in rows for alias in [r['id']] + r.get('source_ids', [])}
    cards = []
    for row in rows:
        if row['decision'] == 'existing':
            continue
        raw = root / row['local_path']
        source = root / row.get('preview_path', row['local_path'])
        url = row.get('url', '')
        cards.append({
            'id': row['id'], 'sha256': row['sha256'], 'decision': row['decision'], 'reason': row['reason'],
            'width': row.get('width', 0), 'height': row.get('height', 0), 'priority': row.get('priority', 0),
            'preview': quote(Path(os.path.relpath(source, dest)).as_posix()),
            'raw': quote(Path(os.path.relpath(raw, dest)).as_posix()),
            'url': url if urlparse(url).scheme in ('http', 'https') else '',
            'pending': bool(row.get('pending_visual_review')),
            'kind': row.get('last_completed_code') or {'text_poster_map_sign':'T', 'equipment_facility':'E',
                'space_layout':'S', 'project_demonstration':'P'}.get(row['reason'], ''),
            'similar': sorted({aliases[i] for i in row.get('near_duplicate_candidates', []) if i in aliases} - {row['id']}),
        })
    human = read(dest / 'human_reviews.json', {'schema':'innowing-image-review-v1', 'records':[]})
    validate_reviews(human, rows)
    payload = json.dumps({'images': cards, 'human': human['records']}, ensure_ascii=False).replace('<', '\\u003c')
    page = TEMPLATE.read_text(encoding='utf-8').replace('__REVIEW_DATA__', payload)
    (dest / 'review.html').write_text(page, encoding='utf-8')


def apply_reviews(path, dest=DEST):
    rows = read(dest / 'decisions.json')
    incoming = validate_reviews(read(path), rows)
    previous = validate_reviews(read(dest / 'human_reviews.json', {'schema':'innowing-image-review-v1', 'records':[]}), rows)
    previous.update(incoming)
    effective = []
    for source in rows:
        row = dict(source)
        if row['id'] in previous:
            review = previous[row['id']]
            row.update(ai_decision=row['decision'], decision=review['decision'], human_review=review,
                       resolved_by_human=True)
        effective.append(row)
    save(dest / 'human_reviews.json', {'schema':'innowing-image-review-v1', 'records':list(previous.values())})
    for kind in ('keep', 'review', 'defer'):
        save(dest / f'reviewed_{kind}.json', [r for r in effective if r['decision'] == kind])
    render_review(rows, dest)
    print(json.dumps({'human_decisions':len(previous), 'imported':len(incoming),
                      'effective_keep':sum(r['decision']=='keep' for r in effective)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['build', 'apply'])
    parser.add_argument('--input', type=Path)
    args = parser.parse_args()
    if args.stage == 'apply':
        if not args.input:
            parser.error('apply requires --input exported_review.json')
        apply_reviews(args.input)
    else:
        render_review(read(DEST / 'decisions.json'))
        print(DEST / 'review.html')
