from pathlib import Path
import tempfile
import unittest
from workflow_fixtures import fixture
from import_legacy_packet import import_packet
from workflow_common import write_json,read_json,WorkflowError,digest
from PIL import Image


class LegacyImportTests(unittest.TestCase):
    def test_snapshots_only_diagram_evidence_and_independent_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            f=fixture(temporary);root=f['root'];legacy=root/'legacy';legacy.mkdir()
            (legacy/'build_packet.py').write_text('raise RuntimeError("Historical code must never run")')
            image_root=root/'legacy-images';image_root.mkdir();path=image_root/'figure.png';Image.new('RGB',(150,100),'white').save(path)
            for n in range(1,6):
                page=[['title',f'Anonymous book {n}'],['p','Synthetic text']]
                if n==4:page.append(['image',{'path':str(path),'width':200,'height':100}])
                write_json(legacy/f'{n:02}_book/content.json',[page])
            args=(legacy,f['sources'],f['catalog'],f['profile'],root/'imported.json',root/'assets')
            with self.assertRaises(WorkflowError):import_packet(*args,legacy_asset_root=image_root)
            self.assertFalse((root/'imported.json').exists())
            report=import_packet(*args,legacy_asset_root=image_root,confirm_independent_diagrams=True)
            self.assertFalse(report['newly_read_originals']);packet=read_json(root/'imported.json')
            diagram=packet['documents'][3]['pages'][0][-1]
            self.assertEqual(diagram['kind'],'diagram');self.assertTrue(diagram['content']['no_hint_confirmed'])
            self.assertEqual(diagram['content']['sha256'],digest(path.read_bytes()))
            self.assertTrue((root/'assets/import-provenance.json').is_file())
            self.assertEqual(report,import_packet(*args,legacy_asset_root=image_root,confirm_independent_diagrams=True))


if __name__=='__main__':unittest.main()
