"""Offline preparation and strict aggregation of Luna visual screening (no descriptions)."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from build.prepare_image_batch import ROOT, RAW, OUT, Image, ImageOps, read, save, safe_path
from PIL import ImageDraw

DEST = OUT / 'selection'
PREVIEWS = RAW / 'selection_previews'
CODES = {
    'T': ('keep', 'text_poster_map_sign'),
    'E': ('keep', 'equipment_facility'),
    'S': ('keep', 'space_layout'),
    'P': ('keep', 'project_demonstration'),
    'D': ('defer', 'generic_event_portrait_decoration'),
    'R': ('review', 'uncertain_or_insufficient_preview'),
}

def prepare():
    DEST.mkdir(parents=True, exist_ok=True)
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    assets = read(OUT / 'bulk/screening.json')['assets']
    rows, candidates, pixels = [], [], {}
    for a in assets:
        row = dict(a)
        row['quality_flags'] = []
        rows.append(row)
        if a['source_type'] == 'physical_photo' or a['screening'] in ('already_reviewed', 'pilot_described'):
            row.update(decision='existing', reason='previously_processed_or_local_collection', decided_by='script')
            continue
        if a.get('decode_state') != 'decoded' or a.get('frames', 1) > 1:
            row.update(decision='review', reason='format_size_or_animation_requires_separate_review', decided_by='script')
            continue
        if min(a['width'], a['height']) < 200:
            row['quality_flags'].append('short_edge_under_200')
        if max(a['width'], a['height']) < 400:
            row['quality_flags'].append('long_edge_under_400')
        try:
            path = safe_path(a['local_path'])
            if hashlib.sha256(path.read_bytes()).hexdigest() != a['sha256']:
                raise ValueError('source_hash_changed')
            with Image.open(path) as src:
                rgba = ImageOps.exif_transpose(src).convert('RGBA')
                # Only identical decoded pixels at identical dimensions are auto-merged.
                fingerprint = hashlib.sha256(str(rgba.size).encode() + rgba.tobytes()).hexdigest()
                if fingerprint in pixels:
                    row.update(decision='defer', reason='identical_decoded_pixels', duplicate_of=pixels[fingerprint], decided_by='script')
                    continue
                pixels[fingerprint] = a['id']
                im = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')
                im.thumbnail((768, 768))
                preview = PREVIEWS / (a['sha256'] + '.jpg')
                im.save(preview, quality=85)
            row['preview_path'] = preview.relative_to(ROOT).as_posix()
            candidates.append(row)
        except Exception as exc:
            row.update(decision='review', reason='preview_error:' + type(exc).__name__, decided_by='script')
    # Related filenames appear near each other, but similarity alone never removes an asset.
    candidates.sort(key=lambda a: a.get('url', ''))
    sheets = []
    for offset in range(0, len(candidates), 48):
        batch = candidates[offset:offset + 48]
        number = len(sheets)
        canvas = Image.new('RGB', (2048, 1440), 'white')
        draw = ImageDraw.Draw(canvas)
        for j, row in enumerate(batch):
            x, y = (j % 8) * 256, (j // 8) * 240
            with Image.open(ROOT / row['preview_path']) as preview:
                thumb = ImageOps.contain(preview, (250, 208))
                canvas.paste(thumb, (x + (256-thumb.width)//2, y + 24 + (208-thumb.height)//2))
            draw.text((x+4, y+4), f"{j+1:02d}  {row['width']}x{row['height']}", fill='black')
            row.update(sheet=number, tile=j+1)
        path = PREVIEWS / f'sheet-{number:03d}.jpg'
        canvas.save(path, quality=90)
        sheets.append({'sheet': number, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'ids': [r['id'] for r in batch]})
    save(DEST / 'assets.json', rows)
    save(DEST / 'sheets.json', sheets)
    for worker in range(3):
        save(DEST / f'assignment-{worker}.json', [s for s in sheets if s['sheet'] % 3 == worker])
    print(json.dumps({'assets':len(rows), 'visual_candidates':len(candidates), 'sheets':len(sheets),
                      'script_decisions':dict(Counter(r.get('decision', 'pending_ai') for r in rows))}), flush=True)

def repair_transparency():
    """Re-review legacy RGB previews with actual transparency, retaining the first audit trail."""
    rows, sheets = read(DEST / 'assets.json'), read(DEST / 'sheets.json')
    if any(s.get('supersedes_preview') for s in sheets):
        raise ValueError('Transparency supplement already prepared')
    by_id = {r['id']: r for r in rows}
    affected = []
    for row in rows:
        if row.get('decision') == 'existing' or row.get('decode_state') != 'decoded' or row.get('frames', 1) > 1:
            continue
        with Image.open(safe_path(row['local_path'])) as src:
            if 'A' not in src.getbands() and 'transparency' not in src.info:
                continue
            rgba = ImageOps.exif_transpose(src).convert('RGBA')
            if rgba.getchannel('A').getextrema()[0] == 255:
                continue
            if row.get('duplicate_of'):
                with Image.open(safe_path(by_id[row['duplicate_of']]['local_path'])) as other:
                    other = ImageOps.exif_transpose(other).convert('RGBA')
                    if rgba.size == other.size and rgba.tobytes() == other.tobytes():
                        row['alpha_duplicate_verified'] = True
                        continue
                for key in ('decision', 'reason', 'decided_by', 'duplicate_of'):
                    row.pop(key, None)
            im = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('RGB')
            im.thumbnail((768, 768))
            path = PREVIEWS / (row['sha256'] + '-white.jpg')
            im.save(path, quality=85)
            row.update(preview_path=path.relative_to(ROOT).as_posix(), alpha_composited=True)
            affected.append(row)
    supplement = []
    for offset in range(0, len(affected), 48):
        batch, number = affected[offset:offset+48], len(sheets)
        canvas = Image.new('RGB', (2048, 1440), 'white')
        draw = ImageDraw.Draw(canvas)
        for j, row in enumerate(batch):
            x, y = (j % 8) * 256, (j // 8) * 240
            with Image.open(ROOT / row['preview_path']) as preview:
                thumb = ImageOps.contain(preview, (250, 208))
                canvas.paste(thumb, (x+(256-thumb.width)//2, y+24+(208-thumb.height)//2))
            draw.text((x+4, y+4), f"{j+1:02d}  {row['width']}x{row['height']}", fill='black')
            row.update(sheet=number, tile=j+1)
        path = PREVIEWS / f'sheet-{number:03d}.jpg'
        canvas.save(path, quality=90)
        sheet = {'sheet': number, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'ids': [r['id'] for r in batch], 'supersedes_preview': True, 'pass_type': 'alpha'}
        sheets.append(sheet)
        supplement.append(sheet)
    save(DEST / 'assets.json', rows)
    save(DEST / 'sheets.json', sheets)
    save(DEST / 'alpha_assignment.json', supplement)
    print(json.dumps({'alpha_rechecks': len(affected), 'supplement_sheets': len(supplement)}))

def prepare_refine(allow_pending=False):
    """Larger previews for source-prioritized images initially deferred by visual triage."""
    rows, sheets = read(DEST / 'assets.json'), read(DEST / 'sheets.json')
    if any(s.get('pass_type') == 'priority_recheck' for s in sheets):
        raise ValueError('Priority refinement already prepared')
    codes = {}
    for s in sheets:
        vote = read(DEST / 'votes' / f"sheet-{s['sheet']:03d}.json")
        if not vote:
            if allow_pending:
                continue
            raise ValueError(f"Missing first-pass sheet {s['sheet']}")
        codes.update(zip(s['ids'], ''.join(''.join(vote['codes']).split())))
        if s.get('supersedes_preview'):
            s['pass_type'] = 'alpha'
    audit = read(DEST / 'audit.json', {})
    if audit:
        for item in audit['items']:
            item['original_code'] = codes[item['id']]
        audit['sampling_note'] = 'Targeted high-priority audit; four initially recorded D labels corrected against normalized original votes.'
        save(DEST / 'audit.json', audit)
    affected = [r for r in rows if codes.get(r['id']) == 'D' and r.get('priority', 0) >= 4]
    affected.sort(key=lambda r: (-r.get('priority', 0), r['id']))
    supplement = []
    for offset in range(0, len(affected), 16):
        batch, number = affected[offset:offset+16], len(sheets)
        canvas = Image.new('RGB', (2048, 1800), 'white')
        draw = ImageDraw.Draw(canvas)
        for j, row in enumerate(batch):
            x, y = (j % 4) * 512, (j // 4) * 450
            with Image.open(ROOT / row['preview_path']) as preview:
                thumb = ImageOps.contain(preview, (504, 415))
                canvas.paste(thumb, (x+(512-thumb.width)//2, y+27+(415-thumb.height)//2))
            draw.text((x+4, y+4), f"{j+1:02d}  {row['width']}x{row['height']}", fill='black')
            row.update(sheet=number, tile=j+1, first_pass_code='D', priority_rechecked=True)
        path = PREVIEWS / f'sheet-{number:03d}.jpg'
        canvas.save(path, quality=92)
        sheet = {'sheet': number, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                 'ids': [r['id'] for r in batch], 'supersedes_preview': True, 'pass_type': 'priority_recheck',
                 'columns': 4, 'rows': 4}
        sheets.append(sheet); supplement.append(sheet)
    save(DEST / 'assets.json', rows)
    save(DEST / 'sheets.json', sheets)
    for worker in range(3):
        save(DEST / f'refine-{worker}.json', supplement[worker::3])
    print(json.dumps({'priority_rechecks':len(affected), 'sheets':len(supplement)}))

def finalize(allow_pending=False):
    rows = read(DEST / 'assets.json')
    sheets = read(DEST / 'sheets.json')
    decisions = {}
    pending, inspected_ids, missing_sheets = {}, set(), []
    inspected_tiles = 0
    for sheet in sheets:
        result = read(DEST / 'votes' / f"sheet-{sheet['sheet']:03d}.json")
        if not result:
            if allow_pending:
                missing_sheets.append(sheet['sheet'])
                for ident in sheet['ids']:
                    pending.setdefault(ident, decisions.get(ident))
                    decisions[ident] = 'R'
                continue
            raise ValueError(f"Missing visual review for sheet {sheet['sheet']}")
        if (result.get('sheet') != sheet['sheet'] or result.get('ids') != sheet['ids']
                or result.get('sheet_sha256') != sheet['sha256'] or result.get('inspected') is not True):
            raise ValueError('Visual review is not bound to the current sheet IDs')
        codes = ''.join(''.join(result['codes']).split())
        if len(codes) != len(sheet['ids']) or set(codes) - set(CODES):
            raise ValueError(f"Invalid codes on sheet {sheet['sheet']}")
        if result.get('model') != 'gpt-6-luna' or result.get('reasoning_effort') != 'medium':
            raise ValueError('Unexpected model attribution')
        for ident, code in zip(sheet['ids'], codes):
            if ident in decisions and not sheet.get('supersedes_preview'):
                raise ValueError('Duplicate visual decision')
            decisions[ident] = code
            inspected_ids.add(ident)
            pending.pop(ident, None)
        inspected_tiles += len(sheet['ids'])
    for row in rows:
        if 'sheet' in row:
            code = decisions[row['id']]
            decision, reason = CODES[code]
            row.update(decision=decision, reason=reason, decided_by='gpt-6-luna', reasoning_effort='medium')
            if decision == 'keep' and 'long_edge_under_400' in row['quality_flags']:
                row.update(decision='review', reason='valuable_but_small_original')
            if row['id'] in pending:
                row.update(decision='review', reason='pending_visual_recheck', decided_by='script_pending_ai',
                           pending_visual_review=True, last_completed_code=pending[row['id']])
    audit = read(DEST / 'audit.json', {})
    audit_items = audit.get('items', [])
    if audit_items:
        if audit.get('model') != 'gpt-6-luna' or audit.get('reasoning_effort') != 'medium':
            raise ValueError('Unexpected audit model')
        by_id = {r['id']: r for r in rows}
        for item in audit_items:
            row = by_id[item['id']]
            if item.get('sha256') != row['sha256'] or item.get('inspected') is not True:
                raise ValueError('Audit image provenance mismatch')
            audit_decision, _ = CODES[item['audit_code']]
            row['audit_code'] = item['audit_code']
            if row['decision'] != audit_decision and not row.get('pending_visual_review'):
                row.update(decision='review', reason='disagreement_in_targeted_quality_check')
    assert len({r['id'] for r in rows}) == len(rows)
    for decision in ('keep', 'review', 'defer', 'existing'):
        save(DEST / f'{decision}.json', [r for r in rows if r['decision'] == decision])
    summary = {'total_assets': len(rows), 'ai_reviewed': len(inspected_ids),
               'complete': not missing_sheets, 'missing_sheets': missing_sheets,
               'pending_visual_images': len(pending),
               'visual_tile_inspections': inspected_tiles,
               'planned_visual_tile_inspections': sum(len(s['ids']) for s in sheets),
               'alpha_preview_rechecks_completed': sum(len(s['ids']) for s in sheets if s.get('pass_type', 'alpha' if s.get('supersedes_preview') else '') == 'alpha' and s['sheet'] not in missing_sheets),
               'high_priority_deferred_rechecks_planned': sum(len(s['ids']) for s in sheets if s.get('pass_type') == 'priority_recheck'),
               'targeted_quality_audit_images': len(audit_items),
               'decisions': dict(Counter(r['decision'] for r in rows)),
               'reasons': dict(Counter(r['reason'] for r in rows)),
               'model': 'gpt-6-luna', 'reasoning_effort': 'medium',
               'descriptions_generated': 0, 'database_modified': False,
               'limitations': ['Contact-sheet content triage; not OCR or full-resolution text verification.',
                              'Near-similarity is not identity; retained candidates may still overlap.',
                              'Existing local and previously described images were not reclassified.']}
    save(DEST / 'summary.json', summary)
    save(DEST / 'decisions.json', rows)
    from build.review_image_candidates import render_review
    render_review(rows, DEST, ROOT)
    print(json.dumps(summary), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'repair-transparency', 'refine', 'finalize'])
    parser.add_argument('--allow-pending', action='store_true', help='Explicit partial output: missing visual votes become review, never keep')
    args = parser.parse_args()
    if args.stage in ('refine', 'finalize'):
        {'refine': prepare_refine, 'finalize': finalize}[args.stage](allow_pending=args.allow_pending)
    else:
        {'prepare': prepare, 'repair-transparency': repair_transparency}[args.stage]()
