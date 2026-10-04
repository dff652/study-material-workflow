"""Generate a private anonymous batch and exercise the offline workflow."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from PIL import Image,ImageDraw
from workflow_common import WorkflowArgumentParser,cli_result,read_json,write_json,digest,canonical,fail,root_path
from workflow import prepare,render,inspect_run


def make_demo(output_root,font_config):
    root=root_path(output_root,must_exist=False);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    source=root/'sources';source.mkdir(exist_ok=True,mode=0o700)
    for index,text in [(1,'Example 1: Calculate 1/2 + 1/6.'),(2,'Theory: add fractions using a common denominator.')]:
        image=Image.new('RGB',(640,320),'white');draw=ImageDraw.Draw(image);draw.text((30,30),text,fill='black')
        stream=BytesIO();image.save(stream,format='PNG');raw=stream.getvalue();path=source/f'page{index}.png'
        from workflow_common import assert_no_symlinks
        assert_no_symlinks(path)
        if path.exists():
            if path.read_bytes()!=raw:fail('demo_conflict','Existing anonymous source differs; use a new demo directory')
        else:
            with path.open('xb') as f:f.write(raw)
            path.chmod(0o600)
    selection={'batch_id':'anonymous-demo-v1','files':[{'path':f'page{n}.png','book':'J1','token':f'{n:06d}','page_order':n} for n in [1,2]],
               'expected_counts':{'sources':2,'parent_questions':1,'entries':1}}
    rows=[{'book':'J1','num':'1','group':1,'photo':'000001','feature':'分数相加的匿名合成题','method':'通分后相加','tag':'示例','tip':'不代表真实学习效果','aux':''}]
    skill=Path(__file__).resolve().parent.parent;profile=skill/'references/calculation-profile.json'
    write_json(root/'selection.json',selection);write_json(root/'raw-catalog.json',rows)
    base=SimpleNamespace(source_root=str(source),selection=str(root/'selection.json'),raw_catalog=str(root/'raw-catalog.json'),profile=str(profile),output_root=str(root/'run'))
    prepare(base)
    sources=read_json(root/'run/inputs/sources.json');catalog=read_json(root/'run/inputs/catalog.json')
    packet=read_json(skill/'assets/example-packet.json');packet['batch_id']=selection['batch_id']
    packet['sources_sha256']=digest(canonical(sources));packet['catalog_sha256']=digest(canonical(catalog))
    for document in packet['documents']:document['source'].update(source_id=packet['batch_id'],sha256=packet['catalog_sha256'])
    write_json(root/'packet.json',packet)
    args=SimpleNamespace(source_root=str(source),sources=str(root/'run/inputs/sources.json'),catalog=str(root/'run/inputs/catalog.json'),packet=str(root/'packet.json'),
                         font_config=str(font_config),profile=str(profile),asset_root=None,output_root=str(root/'run'))
    result=render(args);report=inspect_run(SimpleNamespace(run=str(root/'run/run.json'),source_root=str(source)),True)
    return {**result,'verification':report,'synthetic_sources':True,'ocr':'not_tested','learning_effect':'not_tested','published':False}


def main():
    parser=WorkflowArgumentParser(description=__doc__);parser.add_argument('--output-root',required=True);parser.add_argument('--font-config',required=True)
    args=parser.parse_args();return make_demo(args.output_root,args.font_config)


if __name__=='__main__':raise SystemExit(cli_result(main))
