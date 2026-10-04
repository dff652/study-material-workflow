"""Create a checked private ZIP outside an immutable rendered version."""
from io import BytesIO
import os
from pathlib import Path
import tempfile
import zipfile
from workflow_common import WorkflowArgumentParser,cli_result,read_json,write_json,digest,canonical,fail,assert_no_symlinks,ensure_output_outside
from packet import validate_packet
from verify_packet import verify_packet


def bundle_packet(version_dir,output,sources=None,catalog=None):
    root=Path(version_dir);verify_packet(root);ensure_output_outside(root,output)
    packet=read_json(root/'packet.json')
    if (sources is None)!=(catalog is None):fail('missing_input','Source and catalog snapshots must be supplied together')
    validate_packet(packet,sources,catalog)
    contents={str(p.relative_to(root)):p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}
    if sources is not None:
        contents['inputs/sources.json']=canonical(sources)+b'\n';contents['inputs/catalog.json']=canonical(catalog)+b'\n'
    records={name:{'sha256':digest(raw),'size':len(raw)} for name,raw in contents.items()}
    if sum(v['size'] for v in records.values())>128*1024*1024:fail('bundle_too_large','Bundle exceeds the bounded export size')
    contents['bundle-files.json']=canonical({'schema_version':'swf.bundle-files.v1','files':records})+b'\n'
    stream=BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,raw in sorted(contents.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o600<<16;archive.writestr(info,raw)
    raw=stream.getvalue()
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        if archive.testzip() is not None or set(archive.namelist())!=set(contents):fail('bundle_invalid','ZIP verification failed')
        for name,expected in contents.items():
            if archive.read(name)!=expected:fail('bundle_invalid','ZIP bytes differ from the verified input')
    output=Path(output);assert_no_symlinks(output);output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    reused=output.exists()
    if reused:
        if not output.is_file() or output.read_bytes()!=raw:fail('output_conflict','Existing ZIP differs; use a new output version')
    else:
        fd,temporary=tempfile.mkstemp(prefix='.bundle-',dir=output.parent)
        try:
            with os.fdopen(fd,'wb') as f:os.fchmod(f.fileno(),0o600);f.write(raw);f.flush();os.fsync(f.fileno())
            try:os.link(temporary,output)
            except FileExistsError:
                if output.read_bytes()!=raw:fail('output_conflict','Concurrent ZIP differs')
        finally:Path(temporary).unlink(missing_ok=True)
    checksum={'schema_version':'swf.bundle.v1','zip_sha256':digest(raw),'zip_size':len(raw),'files':len(contents),
              'recipe_sha256':read_json(root/'render-manifest.json')['recipe_sha256']}
    write_json(str(output)+'.checksum.json',checksum)
    return {'output':str(output),'reused':reused,**checksum}


def main():
    parser=WorkflowArgumentParser(description=__doc__)
    parser.add_argument('--version-dir',required=True);parser.add_argument('--output',required=True);parser.add_argument('--sources');parser.add_argument('--catalog');args=parser.parse_args()
    return bundle_packet(args.version_dir,args.output,read_json(args.sources) if args.sources else None,read_json(args.catalog) if args.catalog else None)


if __name__=='__main__':raise SystemExit(cli_result(main))
