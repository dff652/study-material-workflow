"""Dependencies and a locked, private mutable pointer to immutable versions."""
import contextlib
import fcntl
import importlib.metadata
import os
from pathlib import Path
from workflow_common import read_json,write_json,digest,fail,root_path,assert_no_symlinks


@contextlib.contextmanager
def run_lock(root):
    root=Path(root);assert_no_symlinks(root);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=root/'.workflow.lock';assert_no_symlinks(path)
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a+b') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        yield


def file_record(path):
    path=Path(path);assert_no_symlinks(path)
    if not path.is_file():fail('missing_input','Required file is missing')
    return {'path':str(path.resolve()),'sha256':digest(path.read_bytes())}


def tool_records():
    root=Path(__file__).parent
    files=sorted(root.glob('*.py'))
    files+=sorted((root/'print_backend').glob('*.py'))
    return {str(p.relative_to(root)):digest(p.read_bytes()) for p in files}


def environment_records():
    return {name:importlib.metadata.version(name) for name in ['Pillow','reportlab','python-docx','fonttools','lxml','PyMuPDF']}


def check_dependencies(run,source_root=None):
    from collect_sources import verify_sources
    changed=[]
    for key,record in run['inputs'].items():
        try:
            current=file_record(record['path'])
        except (OSError,ValueError):changed.append(key);continue
        if current!=record:changed.append(key)
    if run.get('tool_hashes') and run['tool_hashes']!=tool_records():changed.append('tools')
    if run.get('environment') and run['environment']!=environment_records():changed.append('environment')
    if source_root is not None:
        sources=read_json(run['inputs']['sources']['path'])
        try:verify_sources(sources,source_root)
        except (OSError,ValueError):changed.append('original_source_bytes')
    if changed:fail('stale_run','Changed dependencies: '+', '.join(changed))
    return True


def save_run(root,run):
    write_json(Path(root)/'run.json',run,replace=True)


def load_run(path):
    run=read_json(path)
    if not isinstance(run,dict) or run.get('schema_version')!='swf.run.v1' or not isinstance(run.get('inputs'),dict):
        fail('invalid_run','Unsupported run state')
    return run
