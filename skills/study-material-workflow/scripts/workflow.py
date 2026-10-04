"""Explicit prepare/render/verify/status; no model, database or implicit publish."""
from workflow_common import WorkflowArgumentParser
import argparse
from pathlib import Path
from workflow_common import cli_result,read_json,write_json,digest,canonical,fail,ensure_output_outside,WorkflowError,root_path
from run_state import run_lock,file_record,tool_records,environment_records,check_dependencies,save_run,load_run
from packet import validate_packet


def prepare(args):
    from collect_sources import collect_sources
    from adapt_catalog import adapt_catalog
    root=root_path(args.output_root,must_exist=False);ensure_output_outside(args.source_root,root)
    with run_lock(root):
        sources=collect_sources(args.source_root,read_json(args.selection))
        profile=read_json(args.profile);catalog=adapt_catalog(read_json(args.raw_catalog),sources,profile)
        write_json(root/'inputs/sources.json',sources);write_json(root/'inputs/catalog.json',catalog)
        records={name:file_record(path) for name,path in [('sources',root/'inputs/sources.json'),('catalog',root/'inputs/catalog.json'),
                     ('profile',args.profile),('selection',args.selection),('raw_catalog',args.raw_catalog)]}
        state={'schema_version':'swf.run.v1','batch_id':sources['batch_id'],'stage':'prepared','inputs':records,
               'source_root':str(Path(args.source_root).resolve()),'versions':[],'pending':['agent_reading','content_and_math_review']}
        existing=root/'run.json'
        if existing.exists():
            old=load_run(existing);check_dependencies(old,args.source_root)
            for key,record in records.items():
                if old['inputs'].get(key)!=record:fail('run_conflict','Prepared scope changed; use a new run directory')
            state=old
        save_run(root,state)
    return {'run':str(root/'run.json'),'counts':catalog['counts'],'stage':state['stage']}


def render(args):
    from collect_sources import verify_sources
    from adapt_catalog import adapt_catalog
    from render_packet import render_packet
    root=root_path(args.output_root,must_exist=False);ensure_output_outside(args.source_root,root)
    sources,catalog,packet=read_json(args.sources),read_json(args.catalog),read_json(args.packet)
    verify_sources(sources,args.source_root);validate_packet(packet,sources,catalog)
    profile_path=args.profile or str(Path(__file__).parent.parent/'references'/(catalog['namespace']+'-profile.json'))
    profile=read_json(profile_path)
    if canonical(adapt_catalog([e['raw'] for e in catalog['entries']],sources,profile))!=canonical(catalog):
        fail('stale_catalog','Catalog differs from current explicit profile')
    font_config=read_json(args.font_config)
    records={name:file_record(path) for name,path in [('sources',args.sources),('catalog',args.catalog),('packet',args.packet),
                     ('font_config',args.font_config),('profile',profile_path)]}
    for name in ['regular_source','bold_source','math_source']:records['font_'+name]=file_record(font_config[name])
    for key,entry in __import__('packet').asset_records(packet,args.asset_root).items():
        records['asset_'+key]=file_record(Path(args.asset_root)/key)
    with run_lock(root):
        existing=root/'run.json';old=load_run(existing) if existing.exists() else None
        if old:
            if old['batch_id']!=packet['batch_id']:fail('run_conflict','Run belongs to another batch')
            # Changes require a new immutable version; do not overwrite any old output.
            preserved={key:value for key,value in old['inputs'].items() if key not in records}
        else:preserved={}
        result=render_packet(packet,font_config,root/'versions',asset_root=args.asset_root)
        state={'schema_version':'swf.run.v1','batch_id':packet['batch_id'],'stage':'rendered','inputs':{**preserved,**records},
               'source_root':str(Path(args.source_root).resolve()),'tool_hashes':tool_records(),'environment':environment_records(),'versions':list(old['versions']) if old else [],
               'active_version':str(Path(result['directory']).resolve()),'pending':['content_and_math_review','all_page_visual_review','word_client']}
        if state['active_version'] not in state['versions']:state['versions'].append(state['active_version'])
        save_run(root,state)
    return {**result,'run':str(root/'run.json'),'stage':'rendered'}


def inspect_run(args,verify=False):
    from verify_packet import verify_packet
    path=Path(args.run);root=path.parent
    with run_lock(root):
        state=load_run(path);source_root=args.source_root or state.get('source_root')
        check_dependencies(state,source_root)
        if 'active_version' not in state:
            return {'stage':state['stage'],'pending':state['pending'],'rendered':False}
        report=verify_packet(state['active_version'])
        if verify:
            state['stage']='machine_verified';save_run(root,state)
            write_json(root/'verification.json',report,replace=True)
        return {**report,'stage':state['stage'],'pending':state['pending'],'human_review_approved':False}


def main():
    parser=WorkflowArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('prepare')
    for name in ['source-root','selection','raw-catalog','profile','output-root']:p.add_argument('--'+name,required=True)
    r=commands.add_parser('render')
    for name in ['packet','sources','catalog','source-root','output-root','font-config']:r.add_argument('--'+name,required=True)
    r.add_argument('--asset-root');r.add_argument('--profile')
    for name in ['verify','status']:
        item=commands.add_parser(name);item.add_argument('--run',required=True);item.add_argument('--source-root')
    args=parser.parse_args()
    try:
        if args.command=='prepare':return prepare(args)
        if args.command=='render':return render(args)
        return inspect_run(args,args.command=='verify')
    except WorkflowError as exc:
        # Keep the last successful run pointer; append a failure for safe diagnosis.
        if args.command in {'prepare','render'}:
            root=Path(args.output_root)
            try:
                ensure_output_outside(args.source_root,root)
                failure={'schema_version':'swf.failure.v1','stage':args.command,'code':exc.code,'message':str(exc)}
                with run_lock(root):write_json(root/'failures'/(digest(canonical(failure))[:24]+'.json'),failure)
            except (OSError,ValueError):pass
        raise


if __name__=='__main__':raise SystemExit(cli_result(main))
