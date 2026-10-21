import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from build import describe_priority_images as batch


class PriorityDescriptionTests(unittest.TestCase):
    def fixture(self, directory):
        root=Path(directory); folder=root/'prompt_from_web/innoacademy/preparation/priority_descriptions'
        raw=root/'raw.jpg';raw.write_bytes(b'raw sample for hash validation')
        item={'id':'a','sha256':batch.hashlib.sha256(raw.read_bytes()).hexdigest(),
              'local_path':'raw.jpg','url':'https://example.org/image.jpg','category':'equipment_facility',
              'context':[{'source_page':'https://example.org/page','page_title':'A named laboratory'}]}
        record=dict(id='a',sha256=item['sha256'],model='gpt-6-luna',reasoning_effort='low',
            prompt_version=batch.PROMPT_VERSION,viewed=True,suitable=True,title='White cabinet',
            visible_text=['C1'],visual_facts=['A white cabinet has a black handle.'],
            spatial_relations=[],uncertainties=['The room name is not visible.'])
        path=folder/'descriptions/a.json';batch.save(path,record)
        batch.save(folder/'tasks.json',[item])
        batch.save(folder/'release.json',{'released_at':'2026-10-19T00:00:00+00:00','entries':[
            {'id':'a','sha256':item['sha256'],'description_path':path.relative_to(root).as_posix(),
             'description_sha256':batch.hashlib.sha256(path.read_bytes()).hexdigest()}]})
        return root,folder,item,record

    def test_visual_evidence_does_not_include_web_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root,folder,item,record=self.fixture(directory)
            rows,assets=batch.evidence(root)
            self.assertEqual(len(rows),2)
            self.assertNotIn('named laboratory',rows[0]['text'])
            self.assertEqual(rows[0]['metadata']['status'],'model_described')
            self.assertEqual(rows[0]['metadata']['location'],'unknown')
            self.assertEqual(rows[1]['metadata']['evidence_type'],'web_context')
            self.assertIn('named laboratory',rows[1]['text'])

    def test_changed_description_or_source_cannot_be_ingested(self):
        with tempfile.TemporaryDirectory() as directory:
            root,folder,item,record=self.fixture(directory)
            (root/'raw.jpg').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'image changed'):batch.evidence(root)
        with tempfile.TemporaryDirectory() as directory:
            root,folder,item,record=self.fixture(directory)
            record['title']='different';batch.save(folder/'descriptions/a.json',record)
            with self.assertRaisesRegex(ValueError,'description changed'):batch.evidence(root)

    def test_api_model_label_survives_ingestion(self):
        with tempfile.TemporaryDirectory() as directory:
            root,folder,item,record=self.fixture(directory)
            record.update(model='gpt-5-mini',prompt_version=batch.API_PROMPT_VERSION,
                          generator='azure_vision_api',prompt_sha256='a'*64,finish_reason='stop',
                          response_model='gpt-5-mini-2025-08-07',location='unknown from image',
                          objects_and_counts=['One cabinet.'],colours_and_materials=['White cabinet.'])
            path=folder/'descriptions/a.json';batch.save(path,record)
            release=batch.read(folder/'release.json')
            release['entries'][0]['description_sha256']=batch.hashlib.sha256(path.read_bytes()).hexdigest()
            batch.save(folder/'release.json',release)
            rows,assets=batch.evidence(root)
            self.assertTrue(all(r['metadata']['description_model']=='gpt-5-mini' for r in rows))
            self.assertEqual(next(iter(assets.values()))['model'],'gpt-5-mini')

    def test_missing_description_cannot_publish_a_release(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);batch.save(folder/'tasks.json',[{'id':'missing'}])
            with patch.object(batch,'DEST',folder),self.assertRaisesRegex(ValueError,'missing'):
                batch.export()
            self.assertFalse((folder/'release.json').exists())

    def test_wrong_model_or_unviewed_description_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root,folder,item,record=self.fixture(directory)
            for key,value in [('reasoning_effort','medium'),('viewed',False),('model','other')]:
                bad=dict(record);bad[key]=value
                with self.assertRaises(ValueError):batch.validate(bad,item)
