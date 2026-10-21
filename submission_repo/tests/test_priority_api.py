import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from build import describe_priority_api as api
from build import describe_priority_images as batch


class PriorityAPITests(unittest.TestCase):
    def fixture(self, directory):
        root=Path(directory);dest=root/'priority';dest.mkdir()
        raw=root/'a.png';batch.Image.new('RGB',(20,10),'white').save(raw)
        item={'id':'a','sha256':hashlib.sha256(raw.read_bytes()).hexdigest(),
              'local_path':'a.png','category':'equipment_facility'}
        batch.save(dest/'tasks.json',[item])
        batch.save(root/'selection/reviewed_keep.json',[item])
        return root,dest,item

    def payload(self):
        return dict(title='Cabinet',suitable=True,location='unknown from image',
                    objects_and_counts=['One white cabinet is visible.'],visible_text=['C1'],
                    spatial_relations=[],colours_and_materials=['The cabinet is white.'],uncertainties=[])

    def client(self,payload=None,finish='stop'):
        response=SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish,
            message=SimpleNamespace(content=json.dumps(payload or self.payload()),refusal=None))],
            model='gpt-5-mini-2025-08-07',id='response-id',usage=None)
        client=Mock();client.chat.completions.create.return_value=response
        return client

    def luna(self,item):
        return dict(id=item['id'],sha256=item['sha256'],model='gpt-6-luna',reasoning_effort='low',
            prompt_version=batch.PROMPT_VERSION,viewed=True,suitable=True,title='Cabinet',visible_text=[],
            visual_facts=['A cabinet is visible.'],spatial_relations=[],uncertainties=[])

    def test_plan_is_offline_and_preserves_luna_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root,dest,item=self.fixture(directory)
            path=dest/'descriptions/a.json';batch.save(path,self.luna(item));before=path.read_bytes()
            queued,summary=api.plan(dest,root)
            self.assertEqual(queued,[]);self.assertEqual(summary['by_model'],{'gpt-6-luna':1})
            self.assertEqual(before,path.read_bytes());self.assertEqual(summary['network_requests_made'],0)

    def test_corrupt_cache_or_changed_raw_blocks_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root,dest,item=self.fixture(directory)
            path=dest/'descriptions/a.json';path.parent.mkdir();path.write_text('{broken')
            queued,summary=api.plan(dest,root)
            self.assertEqual(summary['blocked'],1);self.assertEqual(queued,[]);self.assertEqual(path.read_text(),'{broken')
        with tempfile.TemporaryDirectory() as directory:
            root,dest,item=self.fixture(directory);(root/'a.png').write_bytes(b'changed')
            self.assertEqual(api.plan(dest,root)[1]['blocked'],1)

    def test_api_record_preserves_actual_model_and_uses_gpt5_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            root,dest,item=self.fixture(directory);payload=self.payload();payload.update(model='fake',id='fake')
            client=self.client(payload)
            result=api.describe(item,client,'gpt-5-mini','complete prompt',root=root)
            self.assertEqual(result['model'],'gpt-5-mini');self.assertEqual(result['id'],'a')
            self.assertEqual(result['response_model'],'gpt-5-mini-2025-08-07')
            self.assertEqual(result['prompt_sha256'],hashlib.sha256(b'complete prompt').hexdigest())
            params=client.chat.completions.create.call_args.kwargs
            self.assertIn('max_completion_tokens',params);self.assertNotIn('temperature',params);self.assertNotIn('max_tokens',params)
            batch.save(dest/'descriptions/a.json',result)
            self.assertEqual(api.plan(dest,root)[1]['by_model'],{'gpt-5-mini':1})

    def test_truncated_and_malformed_responses_not_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            root,dest,item=self.fixture(directory)
            with self.assertRaises(ValueError):api.describe(item,self.client(finish='length'),'gpt-5-mini','prompt',root=root)
            malformed=self.payload();malformed['visible_text']='not an array'
            with self.assertRaises(ValueError):api.describe(item,self.client(malformed),'gpt-5-mini','prompt',root=root)

    def test_v2_cache_is_preserved_after_v3_prompt_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            root,dest,item=self.fixture(directory)
            record=api.describe(item,self.client(),'gpt-5-mini','prompt',root=root)
            self.assertEqual(record['prompt_version'],'equipment-space-api-v3')
            record['prompt_version']='equipment-space-api-v2'
            path=dest/'descriptions/a.json';batch.save(path,record);before=path.read_bytes()
            queued,summary=api.plan(dest,root)
            self.assertFalse(queued);self.assertEqual(summary['cached_skip'],1)
            self.assertEqual(path.read_bytes(),before)
            record['prompt_version']='unknown-version'
            with self.assertRaises(ValueError):batch.validate(record,item)

    def test_403_stops_run_without_writing_description(self):
        with tempfile.TemporaryDirectory() as directory:
            root,dest,item=self.fixture(directory)
            from bot import llm
            fake=Mock();fake.with_options.return_value=fake
            class Denied(Exception):status_code=403
            args=SimpleNamespace(limit=None,timeout=1,retries=2,max_edge=2400,
                max_completion_tokens=6000,reasoning_effort='low')
            with patch.object(llm,'VISION_DEPLOYMENT','gpt-5-mini'),patch.object(llm,'_client',return_value=fake), \
                 patch.object(api,'describe',side_effect=Denied) as describe,patch.object(api,'plan',wraps=api.plan):
                self.assertEqual(api.run(args,dest,root,sleep=Mock()),1)
            self.assertEqual(describe.call_count,1)
            self.assertFalse((dest/'descriptions/a.json').exists())
            self.assertEqual(batch.read(dest/'api_failures.json')['a']['http_status'],403)

    def test_unsuitable_result_is_cached_not_repeated(self):
        with tempfile.TemporaryDirectory() as directory:
            root,dest,item=self.fixture(directory);payload=self.payload()
            payload.update(suitable=False,objects_and_counts=[],colours_and_materials=[],uncertainties=['A generic illustration.'])
            record=api.describe(item,self.client(payload),'gpt-5-mini','prompt',root=root)
            batch.save(dest/'descriptions/a.json',record)
            queued,summary=api.plan(dest,root)
            self.assertFalse(queued);self.assertEqual(summary['cached_skip'],1)
