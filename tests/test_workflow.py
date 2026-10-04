import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import sys
import subprocess
import json
from workflow_fixtures import fixture,review,SCRIPTS
from workflow_common import read_json,write_json,WorkflowError
from workflow import prepare,render,inspect_run
from publish_packet import publish_packet
from bundle_packet import bundle_packet


class WorkflowTests(unittest.TestCase):
    def test_cli_failure_keeps_prepared_state_and_records_reason(self):
        with tempfile.TemporaryDirectory() as temp:
            f=fixture(temp);root=f['root']
            args=SimpleNamespace(source_root=str(f['source_root']),selection=str(root/'selection.json'),raw_catalog=str(root/'raw.json'),profile=str(root/'profile.json'),output_root=str(root/'run'))
            prepare(args);bad=copy.deepcopy(f['packet']);bad['documents'][3]['pages'][0].append({'kind':'p','content':'Leaked answer','role':'answer'})
            write_json(root/'packet.json',bad,replace=True)
            command=[sys.executable,str(SCRIPTS/'workflow.py'),'render','--source-root',str(f['source_root']),'--sources',str(root/'sources.json'),
                     '--catalog',str(root/'catalog.json'),'--packet',str(root/'packet.json'),'--font-config',str(SCRIPTS.parent/'assets/font-config.example.json'),'--output-root',str(root/'run')]
            result=subprocess.run(command,capture_output=True,text=True,check=False)
            self.assertEqual(result.returncode,2);self.assertEqual(result.stderr,'')
            self.assertEqual(json.loads(result.stdout)['code'],'independent_hint')
            self.assertEqual(read_json(root/'run/run.json')['stage'],'prepared')
            failures=list((root/'run/failures').glob('*.json'));self.assertEqual(len(failures),1)
            self.assertEqual(read_json(failures[0])['code'],'independent_hint')

    def test_prepare_replay_and_original_change_invalidate_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            f=fixture(temp);root=f['root'];args=SimpleNamespace(source_root=str(f['source_root']),selection=str(root/'selection.json'),raw_catalog=str(root/'raw.json'),profile=str(root/'profile.json'),output_root=str(root/'run'))
            a=prepare(args);self.assertEqual(a,prepare(args))
            state=read_json(root/'run/run.json');self.assertEqual(state['pending'],['agent_reading','content_and_math_review'])
            path=f['source_root']/'page1.png';path.write_bytes(path.read_bytes()+b'changed')
            with self.assertRaises(WorkflowError):prepare(args)

    def test_render_verify_resume_publish_and_stale_inputs(self):
        font_config=read_json(SCRIPTS.parent/'assets/font-config.example.json')
        if not all(Path(font_config[name]).is_file() for name in ['regular_source','bold_source','math_source']):self.skipTest('Explicit example fonts are unavailable; configure fonts for integration acceptance')
        with tempfile.TemporaryDirectory() as temp:
            f=fixture(temp);root=f['root'];write_json(root/'fonts.json',font_config)
            prep=SimpleNamespace(source_root=str(f['source_root']),selection=str(root/'selection.json'),raw_catalog=str(root/'raw.json'),profile=str(root/'profile.json'),output_root=str(root/'run'))
            prepare(prep)
            args=SimpleNamespace(source_root=str(f['source_root']),sources=str(root/'run/inputs/sources.json'),catalog=str(root/'run/inputs/catalog.json'),packet=str(root/'packet.json'),font_config=str(root/'fonts.json'),profile=str(root/'profile.json'),asset_root=None,output_root=str(root/'run'))
            result=render(args);self.assertEqual(result['directory'],render(args)['directory'])
            bundle=bundle_packet(result['directory'],root/'packet.zip',f['sources'],f['catalog'])
            self.assertFalse(bundle['reused']);self.assertTrue(bundle_packet(result['directory'],root/'packet.zip',f['sources'],f['catalog'])['reused'])
            inspect=SimpleNamespace(run=str(root/'run/run.json'),source_root=str(f['source_root']))
            report=inspect_run(inspect,True);self.assertEqual(report['status'],'passed');self.assertFalse(report['human_review_approved'])
            accepted=review(f['packet'],result['recipe_sha256'])
            published=publish_packet(result['directory'],accepted,root/'delivery','v1')
            self.assertFalse(published['reused']);self.assertTrue(publish_packet(result['directory'],accepted,root/'delivery','v1')['reused'])
            with self.assertRaises(WorkflowError):publish_packet(result['directory'],accepted,Path(result['directory'])/'delivery','bad')
            changed=copy.deepcopy(f['packet']);changed['documents'][0]['pages'][0][1]['content']+=' 新字形：铮。'
            write_json(root/'packet.json',changed,replace=True)
            with self.assertRaises(WorkflowError):inspect_run(inspect)
            updated=render(args);self.assertNotEqual(updated['directory'],result['directory'])
            state=read_json(root/'run/run.json');self.assertEqual(len(state['versions']),2)
            self.assertTrue(Path(result['directory']).is_dir())
            with self.assertRaises(WorkflowError):publish_packet(updated['directory'],accepted,root/'delivery','v2')
            # Immutable payload tampering blocks a continuation and publication.
            manifest=read_json(Path(updated['directory'])/'render-manifest.json')
            pdf=Path(updated['directory'])/manifest['documents'][0]['pdf'];pdf.write_bytes(pdf.read_bytes()+b'tampered')
            with self.assertRaises(WorkflowError):inspect_run(inspect)


if __name__=='__main__':unittest.main()
