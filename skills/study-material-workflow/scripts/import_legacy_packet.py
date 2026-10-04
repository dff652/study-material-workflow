"""Read JSON content snapshots, never execute their historical Python scripts."""
from workflow_common import WorkflowArgumentParser
import argparse
import shutil
from pathlib import Path
from PIL import Image
from workflow_common import cli_result, read_json, write_json, canonical, digest, fail, resolve_under, ensure_output_outside,root_path,assert_no_symlinks
from packet import validate_packet


PURPOSE_ORDER = ["knowledge_summary", "classification_index", "evidence_report", "independent_practice", "parent_answers"]


def import_packet(content_root, sources, catalog, profile, output, asset_root, *, legacy_asset_root=None,
                  confirm_independent_diagrams=False):
    content_root = root_path(content_root)
    ensure_output_outside(content_root, output)
    ensure_output_outside(content_root, asset_root)
    assets = Path(asset_root);assets.mkdir(parents=True, exist_ok=True, mode=0o700)
    if sources.get("batch_id") != catalog.get("batch_id"):
        fail("batch_conflict", "Sources and catalog must belong to the same batch")
    catalog_sha = digest(canonical(catalog))
    documents=[];provenance={'schema_version':'swf.legacy-provenance.v1','content_snapshots':{},'assets':{}}
    for index,purpose in enumerate(PURPOSE_ORDER,1):
        candidates=list(content_root.glob(f'{index:02}_*/content.json'))
        if len(candidates)!=1:
            fail("invalid_legacy_content", "Each numbered purpose needs exactly one content snapshot")
        source=candidates[0];old=read_json(source);pages=[];independent=purpose=='independent_practice'
        provenance['content_snapshots'][str(source.relative_to(content_root))]=digest(source.read_bytes())
        if not isinstance(old,list):fail('invalid_legacy_content','Content snapshot must contain page arrays')
        for page in old:
            blocks=[]
            if not isinstance(page,list):fail('invalid_legacy_content','Page must contain block arrays')
            for block in page:
                if not isinstance(block,list) or len(block)!=2:fail('invalid_legacy_content','Block must be kind/content pair')
                kind,content=block
                role='title' if kind=='title' else 'instruction' if independent and kind=='sub' else 'answer_space' if independent and kind=='space' else 'question' if independent else 'body'
                if kind=='map' and content is None:
                    topic={'calculation':'计算综合','geometry':'几何综合'}.get(profile['namespace'],'专题学习')
                    content={'root':[topic,'知识与方法'],'groups':[{'label':[name],'detail':['条件→步骤','原图与题目反查']} for name in profile['groups'].values()]}
                if kind=='image':
                    if legacy_asset_root is None:fail('missing_asset_root','Explicit original diagram root is required')
                    assert_no_symlinks(content['path'])
                    original=Path(content['path']).resolve();allowed=root_path(legacy_asset_root)
                    if not original.is_relative_to(allowed):fail('path_escape','Legacy image is outside the allowed diagram root')
                    original=resolve_under(allowed,str(original.relative_to(allowed)))
                    with Image.open(original,formats=['PNG']) as image:
                        image.load();width,height=image.size
                    sha=digest(original.read_bytes());key=sha+'.png';dest=resolve_under(assets,key,must_exist=False)
                    provenance['assets'][key]={'original_storage_key':str(original.relative_to(allowed)),'sha256':sha}
                    vector=original.with_suffix('.pdf')
                    if vector.is_file():
                        vector=resolve_under(allowed,str(vector.relative_to(allowed)))
                        provenance['assets'][key]['vector_source']={'storage_key':str(vector.relative_to(allowed)),'sha256':digest(vector.read_bytes())}
                    if dest.exists():
                        if digest(dest.read_bytes())!=sha:fail('asset_conflict','Asset destination differs')
                    else:shutil.copyfile(original,dest);dest.chmod(0o600)
                    width_points=min(487,float(content.get('width',487)),float(content.get('height',700))*width/height)
                    content={'storage_key':key,'sha256':sha,'source_ref':'历史复测题图' if independent else '历史内容快照中的教学图',
                             'alt':'题目图示' if independent else '资料图示','width_mm':max(10,width_points*25.4/72),
                             'no_hint_confirmed':bool(confirm_independent_diagrams) if independent else False}
                    kind='diagram'
                blocks.append({'kind':kind,'content':content,'role':role})
            pages.append(blocks)
        title=source.parent.name[3:]
        documents.append({'schema_version':'swf.print.v1','document_id':f'{profile["namespace"]}-{index:02}',
                          'title':title,'purpose':purpose,'pages':pages,'source':{'source_id':sources['batch_id'],
                          'sha256':catalog_sha,'state':'legacy_unreviewed','revision_id':None}})
    packet={'schema_version':'swf.packet.v1','batch_id':sources['batch_id'],'sources_sha256':digest(canonical(sources)),
            'catalog_sha256':catalog_sha,'documents':documents,'omitted_purposes':[]}
    validate_packet(packet,sources,catalog);write_json(assets/'import-provenance.json',provenance);write_json(output,packet)
    return {'packet':str(output),'documents':5,'pages':sum(len(d['pages']) for d in documents),
            'review_state':'legacy_unreviewed','newly_read_originals':False,'provenance':str(assets/'import-provenance.json')}


def main():
    parser=WorkflowArgumentParser(description=__doc__)
    for name in ['content-root','sources','catalog','profile','output','asset-root']:parser.add_argument('--'+name,required=True)
    parser.add_argument('--legacy-asset-root');parser.add_argument('--confirm-independent-diagrams',action='store_true')
    args=parser.parse_args()
    return import_packet(args.content_root,read_json(args.sources),read_json(args.catalog),read_json(args.profile),
                         args.output,args.asset_root,legacy_asset_root=args.legacy_asset_root,
                         confirm_independent_diagrams=args.confirm_independent_diagrams)


if __name__=='__main__':
    raise SystemExit(cli_result(main))
