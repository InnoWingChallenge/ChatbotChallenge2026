import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from build import select_image_candidates as selection


class SelectionTests(unittest.TestCase):
    def test_alpha_difference_is_not_an_exact_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = []
            for i, alpha in enumerate((255, 100, 100)):
                path = root / f'{i}.png'
                selection.Image.new('RGBA', (20, 20), (0, 0, 0, alpha)).save(path)
                assets.append({'id': str(i), 'source_type': 'web_image', 'screening': 'ready_for_description',
                               'local_path': path.name, 'sha256': selection.hashlib.sha256(path.read_bytes()).hexdigest(),
                               'decode_state': 'decoded', 'width': 20, 'height': 20, 'frames': 1})
            selection.save(root / 'bulk/screening.json', {'assets': assets})
            with patch.object(selection, 'ROOT', root), patch.object(selection, 'OUT', root), \
                 patch.object(selection, 'DEST', root / 'selection'), patch.object(selection, 'PREVIEWS', root / 'previews'), \
                 patch.object(selection, 'safe_path', side_effect=lambda p: root / p):
                selection.prepare()
                rows = selection.read(root / 'selection/assets.json')
                self.assertIn('sheet', rows[0])
                self.assertIn('sheet', rows[1])
                self.assertEqual(rows[2]['duplicate_of'], '1')

    def fixture(self, directory, result):
        dest = Path(directory)
        selection.save(dest / 'assets.json', [{'id': 'one', 'sheet': 0, 'sha256': 'hash',
            'local_path': 'one.jpg', 'quality_flags': ['long_edge_under_400']}])
        selection.save(dest / 'sheets.json', [{'sheet': 0, 'ids': ['one'], 'sha256': 'sheet-hash'}])
        if result:
            result = dict(result, sheet=0, ids=['one'], sheet_sha256='sheet-hash', inspected=True)
            selection.save(dest / 'votes/sheet-000.json', result)
        return patch.object(selection, 'DEST', dest)

    def test_missing_visual_review_cannot_silently_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.fixture(directory, None), self.assertRaisesRegex(ValueError, 'Missing'):
                selection.finalize()

    def test_explicit_partial_output_marks_missing_vote_as_pending_review(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.fixture(directory, None), patch.object(selection, 'ROOT', Path(directory)):
                selection.finalize(allow_pending=True)
                summary = selection.read(Path(directory) / 'summary.json')
                self.assertFalse(summary['complete'])
                self.assertEqual(summary['ai_reviewed'], 0)
                self.assertEqual(summary['pending_visual_images'], 1)
                self.assertEqual(selection.read(Path(directory) / 'keep.json'), [])

    def test_bad_vote_count_and_wrong_model_rejected(self):
        for result in ({'codes': 'EE'}, {'codes': 'E', 'model': 'other'}):
            with tempfile.TemporaryDirectory() as directory:
                with self.fixture(directory, result), self.assertRaises(ValueError):
                    selection.finalize()

    def test_valuable_small_image_is_review_not_automatic_keep(self):
        result = {'codes': 'E', 'model': 'gpt-6-luna', 'reasoning_effort': 'medium'}
        with tempfile.TemporaryDirectory() as directory:
            with self.fixture(directory, result), patch.object(selection, 'ROOT', Path(directory)):
                selection.finalize()
                self.assertEqual(selection.read(Path(directory) / 'keep.json'), [])
                review = selection.read(Path(directory) / 'review.json')
                self.assertEqual(review[0]['reason'], 'valuable_but_small_original')
                self.assertEqual(selection.read(Path(directory) / 'summary.json')['descriptions_generated'], 0)
