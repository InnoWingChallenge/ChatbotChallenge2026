import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from build import review_image_candidates as review


class ReviewTests(unittest.TestCase):
    def rows(self):
        return [{'id':'a', 'sha256':'hash-a', 'decision':'review', 'reason':'pending_visual_recheck',
                 'local_path':'a.png', 'pending_visual_review':True},
                {'id':'b', 'sha256':'hash-b', 'decision':'keep', 'reason':'equipment_facility', 'local_path':'b.png'}]

    def payload(self, **kwargs):
        return {'schema':'innowing-image-review-v1','records':[dict(id='a',sha256='hash-a',decision='keep',**kwargs)]}

    def test_stale_hash_or_unknown_id_rejected(self):
        for key,value in [('sha256','stale'),('id','unknown'),('decision','delete')]:
            payload=self.payload();payload['records'][0][key]=value
            with self.assertRaises(ValueError): review.validate_reviews(payload,self.rows())

    def test_duplicate_review_rejected(self):
        payload=self.payload();payload['records']*=2
        with self.assertRaises(ValueError): review.validate_reviews(payload,self.rows())

    def test_apply_keeps_ai_snapshot_and_merges_previous_human_records(self):
        with tempfile.TemporaryDirectory() as directory:
            dest=Path(directory);rows=self.rows()
            review.save(dest/'decisions.json',rows)
            review.save(dest/'human_reviews.json',{'schema':'innowing-image-review-v1','records':[
                {'id':'b','sha256':'hash-b','decision':'defer'}]})
            review.save(dest/'incoming.json',self.payload(note='readable'))
            with patch.object(review,'render_review'):
                review.apply_reviews(dest/'incoming.json',dest)
            self.assertEqual(review.read(dest/'decisions.json'),rows)
            kept=review.read(dest/'reviewed_keep.json')
            self.assertEqual([r['id'] for r in kept],['a'])
            self.assertTrue(kept[0]['resolved_by_human'])
            self.assertEqual(review.read(dest/'reviewed_defer.json')[0]['id'],'b')

    def test_embedded_data_cannot_break_out_of_script_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            dest=Path(directory); rows=self.rows();rows[0]['id']='</script><script>alert(1)</script>'
            review.render_review(rows,dest,dest)
            page=(dest/'review.html').read_text(encoding='utf-8')
            self.assertNotIn(rows[0]['id'],page)
            self.assertIn('\\u003c/script>',page)
