import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from workflow_fixtures import fixture,SCRIPTS
from workflow_common import WorkflowError,read_json
import render_packet
import verify_packet


class RecoveryTests(unittest.TestCase):
    def test_killed_owner_releases_renderer_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'render.lock'
            code="import sys,time;sys.path.insert(0,sys.argv[1]);from render_packet import _acquire_lock;fd=_acquire_lock(sys.argv[2]);print('ready',flush=True);time.sleep(30)"
            process=subprocess.Popen([sys.executable,'-c',code,str(SCRIPTS),str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                ready=select.select([process.stdout],[],[],5)[0];self.assertTrue(ready)
                self.assertEqual(process.stdout.readline().strip(),'ready')
                with self.assertRaises(WorkflowError) as busy:render_packet._acquire_lock(path)
                self.assertEqual(busy.exception.code,'render_in_progress')
                process.kill();process.wait(timeout=5)
                descriptor=render_packet._acquire_lock(path);os.close(descriptor)
                self.assertTrue(path.exists())
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=5)
                process.stdout.close();process.stderr.close()

    def test_failed_render_removes_only_its_stage_then_resumes(self):
        fonts=read_json(SCRIPTS.parent/'assets/font-config.example.json')
        if not all(Path(fonts[k]).is_file() for k in ['regular_source','bold_source','math_source']):self.skipTest('Configured example fonts unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            f=fixture(temporary);versions=f['root']/'versions';versions.mkdir()
            foreign=versions/'.unrelated-stage';foreign.mkdir();(foreign/'keep').write_text('keep')
            with patch.object(render_packet,'render_document',side_effect=WorkflowError('injected_failure','Synthetic interrupted rendering')):
                with self.assertRaises(WorkflowError):render_packet.render_packet(f['packet'],fonts,versions)
            self.assertEqual((foreign/'keep').read_text(),'keep')
            self.assertFalse(list(versions.glob('.*.stage-*')))
            result=render_packet.render_packet(f['packet'],fonts,versions)
            self.assertEqual(verify_packet.verify_packet(result['directory'])['status'],'passed')
            self.assertEqual((foreign/'keep').read_text(),'keep')


if __name__=='__main__':unittest.main()
