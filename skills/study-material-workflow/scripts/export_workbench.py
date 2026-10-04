"""Export through a selected Workbench pure converter; never open its database."""
from workflow_common import WorkflowArgumentParser
import argparse
import os
from pathlib import Path
import subprocess
import sys
from workflow_common import read_json,write_json,canonical,digest,fail,cli_result,root_path,ensure_output_outside,resolve_under


CONVERTER = '''import sys,json
r=json.load(sys.stdin);sys.path.insert(0,r['root'])
from app.domain import SourceImage,serialize_bundle,deserialize_bundle
from app.imports.catalog import build_legacy_bundle
images={}
for s in r['sources']['sources']:
 if s['token'] in images:raise ValueError('Workbench token must be unique across books')
 images[s['token']]=SourceImage(s['source_id'],r['household'],s['sha256'],s['storage_key'],
  'image/png' if s['format']=='PNG' else 'image/jpeg',s['width'],s['height'],r['recorded_at'])
kwargs=dict(household_id=r['household'],dataset_key=r['dataset'],recorded_at=r['recorded_at'])
groups={int(k):v for k,v in r['profile']['groups'].items()}
if r['profile']['namespace']=='geometry':
 from app.imports.geometry import build_geometry_bundle
 conversion=build_geometry_bundle(r['rows'],groups,images,auxiliary_mapping=r['profile']['aux_aliases'],**kwargs)
else:conversion=build_legacy_bundle(r['rows'],groups,images,**kwargs)
saved=serialize_bundle(conversion.bundle);assert deserialize_bundle(saved)==conversion.bundle
print(json.dumps({'bundle':json.loads(saved),'counts':conversion.counts,'database_opened':False}))
'''


def export_bundle(catalog,sources,profile,workbench_root,household,dataset,recorded_at,output):
    from adapt_catalog import adapt_catalog
    rows=[entry['raw'] for entry in catalog['entries']]
    if canonical(adapt_catalog(rows,sources,profile))!=canonical(catalog):
        fail('stale_catalog','Catalog no longer matches its source/profile input')
    root=root_path(workbench_root)
    ensure_output_outside(root,output)
    for value in [household,dataset,recorded_at]:
        if not isinstance(value,str) or not value.strip():fail('invalid_scope','Explicit scope and recorded time are required')
    paths=['app/domain/contracts.py','app/domain/serialization.py','app/imports/catalog.py']
    if profile['namespace']=='geometry':paths.append('app/imports/geometry.py')
    checkpoint={name:digest(resolve_under(root,name).read_bytes()) for name in paths}
    request={'root':str(root),'sources':sources,'profile':profile,'rows':rows,'household':household,'dataset':dataset,'recorded_at':recorded_at}
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    try:
        result=subprocess.run([sys.executable,'-c',CONVERTER],input=canonical(request),capture_output=True,env=env,timeout=60)
    except subprocess.TimeoutExpired:
        fail('adapter_timeout','Selected converter did not finish; no database was opened by this tool')
    if result.returncode:
        fail('adapter_rejected','Current Workbench converter rejected this input; inspect mapping/contract before importing')
    if checkpoint!={name:digest(resolve_under(root,name).read_bytes()) for name in paths}:
        fail('upstream_changed','Workbench converter changed during preparation')
    import json
    converted=json.loads(result.stdout)
    record={'schema_version':'swf.workbench-export.v1','catalog_sha256':digest(canonical(catalog)),
            'upstream_file_hashes':checkpoint,**converted}
    write_json(output,record)
    return {'output':str(output),'counts':record['counts'],'database_opened':False,'review_state':'draft'}


def main():
    parser=WorkflowArgumentParser(description=__doc__)
    for name in ['catalog','sources','profile','workbench-root','household','dataset','recorded-at','output']:parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    return export_bundle(read_json(args.catalog),read_json(args.sources),read_json(args.profile),args.workbench_root,
                         args.household,args.dataset,args.recorded_at,args.output)


if __name__=='__main__':raise SystemExit(cli_result(main))
