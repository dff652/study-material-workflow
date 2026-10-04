import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS=Path(__file__).resolve().parents[1]/'skills/study-material-workflow/scripts';sys.path.insert(0,str(SCRIPTS))
from workflow_common import WorkflowError,read_json,write_json,resolve_under,canonical,digest
from benchmark import compare
from diagrams import draw_scene
from publish_packet import PUBLISH_CODE


class ToolTests(unittest.TestCase):
    def test_conflicts_duplicate_json_and_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);write_json(root/'a.json',{'a':1});self.assertFalse(write_json(root/'a.json',{'a':1}))
            with self.assertRaises(WorkflowError):write_json(root/'a.json',{'a':2})
            (root/'dup.json').write_text('{"x":1,"x":2}')
            with self.assertRaises(WorkflowError):read_json(root/'dup.json')
            with self.assertRaises(WorkflowError):resolve_under(root,'../escape')
            (root/'linked.json').symlink_to(root/'a.json')
            with self.assertRaises(WorkflowError):read_json(root/'linked.json')

    def test_unknowns_and_missing_fields_counted(self):
        truth=[{'id':'q1','task':'handwriting','fields':{'author':'unknown','answer':None}},{'id':'q2','task':'ocr','fields':{'text':'1/2'}}]
        actual=[{'id':'q1','task':'handwriting','fields':{'author':'child'}}]
        result=compare(truth,actual)
        self.assertEqual(result['metrics']['handwriting']['unknowns_invented'],1)
        self.assertEqual(result['metrics']['ocr']['missing_records'],1)
        self.assertEqual(result['real_model'],'not_tested');self.assertIsNone(result['actual_cost_usd'])
        self.assertEqual(len(result['mismatches']),3)

    def test_benchmark_duplicate_and_unobserved_cost(self):
        data=[{'id':'q','task':'ocr','fields':{'text':'x'}}]
        with self.assertRaises(WorkflowError):compare(data*2,data)
        usage={'provider':'fake','model':'fake','request_ids':[],'scope_sha256':'0'*64,'input_tokens':2,'output_tokens':1,
               'actual_cost_usd':None,'evidence_kind':'synthetic'}
        result=compare(data,data,usage);self.assertEqual(result['real_model'],'not_tested')
        usage['actual_cost_usd']='NaN'
        with self.assertRaises(WorkflowError):compare(data,data,usage)

    def test_drawing_resource_and_reuse(self):
        scene={'width':200,'height':140,'source_ref':'synthetic coordinates',
               'elements':[{'kind':'polygon','points':[20,20,180,20,100,110],'color':'#163C65','fill':'#EAF3FA'},
                           {'kind':'text','x':100,'y':112,'text':'A','size':12}]}
        with tempfile.TemporaryDirectory() as root:
            result=draw_scene(scene,root);self.assertEqual(result,draw_scene(scene,root))
            for name,sha in result['files'].items():self.assertEqual(digest((Path(result['directory'])/name).read_bytes()),sha)
            scene['elements'][1]['text']='X'*80
            with self.assertRaises(WorkflowError):draw_scene(scene,root)

    def test_publication_transport_replay_and_conflict(self):
        import base64,io,zipfile
        namespace={};exec(PUBLISH_CODE,namespace);publish=namespace['publish']
        raw=b'original';archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as z:z.writestr('document.pdf',raw)
        files={'document.pdf':{'size':len(raw),'sha256':digest(raw)}}
        receipt={'delivery_id':'a'*64}
        with tempfile.TemporaryDirectory() as root:
            req={'target_root':root,'version_name':'v1','files':files,'receipt':receipt,'archive':base64.b64encode(archive.getvalue()).decode()}
            self.assertFalse(publish(req)['reused']);self.assertTrue(publish(req)['reused'])
            self.assertEqual(json.loads((Path(root)/'workflow-index.json').read_text())['versions'],{'v1':'a'*64})
            (Path(root)/'v1/document.pdf').write_bytes(b'changed')
            with self.assertRaises(ValueError):publish(req)

    def test_publication_repairs_missing_index_and_rejects_foreign_index(self):
        import base64,io,zipfile
        namespace={};exec(PUBLISH_CODE,namespace);publish=namespace['publish']
        data=b'x';archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as z:z.writestr('x',data)
        with tempfile.TemporaryDirectory() as root:
            req={'target_root':root,'version_name':'v1','files':{'x':{'size':1,'sha256':digest(data)}},'receipt':{'delivery_id':'a'*64},'archive':base64.b64encode(archive.getvalue()).decode()}
            publish(req);(Path(root)/'workflow-index.json').unlink();self.assertTrue(publish(req)['reused'])
            (Path(root)/'workflow-index.json').write_text('{"owner":"someone_else"}')
            with self.assertRaises(ValueError):publish(req)

    def test_index_conflict_does_not_create_an_orphan_version(self):
        namespace={};exec(PUBLISH_CODE,namespace)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            index={'schema_version':'swf.delivery-index.v1','versions':{'v1':'a'*64}}
            write_json(root/'workflow-index.json',index)
            request={'target_root':str(root),'version_name':'v1','files':{},'receipt':{'delivery_id':'b'*64},'archive':''}
            with self.assertRaises(ValueError):namespace['publish'](request)
            self.assertFalse((root/'v1').exists())
            self.assertEqual(read_json(root/'workflow-index.json'),index)


if __name__=='__main__':unittest.main()
