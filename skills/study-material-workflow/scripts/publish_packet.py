"""Verified append-only publication to a local root or explicit SSH root."""
from workflow_common import WorkflowArgumentParser
import argparse
import base64
import io
import json
from pathlib import Path
import re
import shlex
import subprocess
import zipfile
from workflow_common import cli_result,read_json,canonical,digest,fail,assert_no_symlinks
from packet import validate_review


# The remote side needs only Python's stdlib. Paths and bytes arrive as JSON stdin,
# never as interpolated shell fragments. The same implementation is tested locally.
PUBLISH_CODE = r'''
import os,json,hashlib,base64,io,zipfile,tempfile,shutil,fcntl,re,ctypes
from pathlib import Path
def sha(v):return hashlib.sha256(v).hexdigest()
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def no_links(p):
 for x in (p,*p.parents):
  if x.is_symlink():raise ValueError('symlink publication path')
def rename_exclusive(source,target):
 libc=ctypes.CDLL(None,use_errno=True);rename=getattr(libc,'renameat2',None)
 if rename is None:raise ValueError('atomic no-replace publication unavailable')
 rename.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint);rename.restype=ctypes.c_int
 if rename(-100,os.fsencode(source),-100,os.fsencode(target),1)!=0:raise OSError(ctypes.get_errno(),'atomic publication refused')
def save(p,v):
 fd,t=tempfile.mkstemp(prefix='.index-',dir=p.parent)
 try:
  with os.fdopen(fd,'wb') as f:os.fchmod(f.fileno(),0o600);f.write(canonical(v)+b'\n');f.flush();os.fsync(f.fileno())
  os.replace(t,p)
 finally:Path(t).unlink(missing_ok=True)
def publish(request):
 version=request['version_name']
 if not isinstance(version,str) or not re.fullmatch(r'[^\x00-\x1f/\\]{1,100}',version) or version.startswith('.'):raise ValueError('invalid version name')
 for key in request['files']:
  path=Path(key)
  if not isinstance(key,str) or '\\' in key or path.is_absolute() or '..' in path.parts or path.as_posix()!=key:raise ValueError('invalid payload path')
 root=Path(request['target_root']).absolute();no_links(root);root.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd=os.open(root/'.swf-publish.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'a+b') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  target=root/request['version_name'];no_links(target)
  index_path=root/'workflow-index.json';no_links(index_path)
  index=json.loads(index_path.read_bytes()) if index_path.exists() else {'schema_version':'swf.delivery-index.v1','versions':{}}
  if index.get('schema_version')!='swf.delivery-index.v1' or not isinstance(index.get('versions'),dict):raise ValueError('foreign index refuses overwrite')
  files=request['files'];receipt=request['receipt']
  previous=index['versions'].get(request['version_name'])
  if previous is not None and previous!=receipt['delivery_id']:raise ValueError('index version conflict')
  def check(directory):
   for p in directory.rglob('*'):no_links(p)
   actual={str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file()}
   if actual!=set(files)|{'delivery-receipt.json'}:raise ValueError('published file set differs')
   for key,record in files.items():
    p=directory/key;no_links(p)
    if p.stat().st_size!=record['size'] or sha(p.read_bytes())!=record['sha256']:raise ValueError('published bytes differ')
   if json.loads((directory/'delivery-receipt.json').read_bytes())!=receipt:raise ValueError('receipt differs')
  reused=target.exists()
  if reused:check(target)
  else:
   temporary=Path(tempfile.mkdtemp(prefix='.swf-staging-',dir=root))
   try:
    data=base64.b64decode(request['archive'],validate=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
     if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=set(files):raise ValueError('archive file set differs')
     if sum(i.file_size for i in z.infolist())>128*1024*1024:raise ValueError('archive too large')
     for key,record in files.items():
      relative=Path(key)
      if relative.is_absolute() or '..' in relative.parts:raise ValueError('archive path escape')
      raw=z.read(key)
      if len(raw)!=record['size'] or sha(raw)!=record['sha256']:raise ValueError('archive hash mismatch')
      p=temporary/relative;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
      with p.open('xb') as f:os.fchmod(f.fileno(),0o600);f.write(raw);f.flush();os.fsync(f.fileno())
    save(temporary/'delivery-receipt.json',receipt);check(temporary)
    if target.exists():raise ValueError('concurrent version conflict')
    rename_exclusive(temporary,target)
   finally:
    if temporary.exists():shutil.rmtree(temporary)
  check(target)
  index['versions'][request['version_name']]=receipt['delivery_id'];save(index_path,index)
  return {'status':'delivered','directory':str(target),'files_verified':len(files),'reused':reused,'delivery_id':receipt['delivery_id']}
'''


def build_request(version_dir,review,target_root,version_name):
    from verify_packet import verify_packet
    root=Path(version_dir);assert_no_symlinks(root)
    source=root.resolve();assert_no_symlinks(target_root);target=Path(target_root).resolve()
    if target.is_relative_to(source) or source.is_relative_to(target):
        fail('publication_overlap','Publication and rendered source trees must be separate')
    report=verify_packet(root)
    if report.get('status')!='passed':fail('not_verified','Machine packet verification must pass')
    manifest=read_json(root/'render-manifest.json');packet=read_json(root/'packet.json')
    validate_review(review,packet,recipe_sha256=manifest['recipe_sha256'],require_verified=True)
    if (not isinstance(version_name,str) or not re.fullmatch(r'[^\x00-\x1f/\\]{1,100}',version_name) or
        version_name.startswith('.') or version_name in {'.','..'}):fail('invalid_version','Use a plain visible version directory name')
    files={};contents={}
    for p in sorted(root.rglob('*')):
        if p.is_file():
            assert_no_symlinks(p);key=str(p.relative_to(root));raw=p.read_bytes()
            if key in {'review.json','delivery-receipt.json'}:fail('foreign_file','Source version contains publication metadata')
            contents[key]=raw;files[key]={'sha256':digest(raw),'size':len(raw)}
    raw=canonical(review)+b'\n';contents['review.json']=raw;files['review.json']={'sha256':digest(raw),'size':len(raw)}
    if sum(v['size'] for v in files.values())>128*1024*1024:fail('publication_too_large','Publication exceeds the bounded payload')
    receipt={'schema_version':'swf.delivery.v1','recipe_sha256':manifest['recipe_sha256'],'files':files,'word_client':review['word_client']}
    receipt['delivery_id']=digest(canonical(receipt))
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for key,data in contents.items():z.writestr(key,data)
    return {'target_root':str(target_root),'version_name':version_name,'files':files,'receipt':receipt,
            'archive':base64.b64encode(archive.getvalue()).decode('ascii')}


def publish_packet(version_dir,review,target_root,version_name,*,ssh_target=None):
    request=build_request(version_dir,review,target_root,version_name)
    if ssh_target is None:
        namespace={};exec(PUBLISH_CODE,namespace)
        try:return namespace['publish'](request)
        except (OSError,ValueError,KeyError,zipfile.BadZipFile) as exc:fail('publication_failed',str(exc))
    if not isinstance(ssh_target,str) or not re.fullmatch(r'[A-Za-z0-9_.@:-]+',ssh_target) or ssh_target.startswith('-'):
        fail('invalid_ssh_target','SSH target must be an explicit account/host without shell syntax')
    command=PUBLISH_CODE+"\nprint(json.dumps(publish(json.load(__import__('sys').stdin)),ensure_ascii=False))\n"
    try:
        result=subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',ssh_target,
                               'python3 -c '+shlex.quote(command)],input=canonical(request),capture_output=True,timeout=120)
    except subprocess.TimeoutExpired:fail('delivery_unknown','Connection timed out; inspect/retry the same identity before any new publication')
    if result.returncode:fail('delivery_unknown','Remote outcome is not confirmed; retry same identity after checking access')
    try:receipt=json.loads(result.stdout)
    except ValueError:fail('delivery_unknown','Remote receipt was not readable; inspect same version')
    if (not isinstance(receipt,dict) or receipt.get('status')!='delivered' or
        receipt.get('delivery_id')!=request['receipt']['delivery_id'] or
        receipt.get('files_verified')!=len(request['files']) or
        receipt.get('directory')!=str(Path(request['target_root']).absolute()/version_name)):
        fail('delivery_unknown','Remote receipt does not match the requested version and bytes')
    return receipt


def main():
    parser=WorkflowArgumentParser(description=__doc__)
    for name in ['version-dir','review','target-root','version-name']:parser.add_argument('--'+name,required=True)
    parser.add_argument('--ssh-target');args=parser.parse_args()
    return publish_packet(args.version_dir,read_json(args.review),args.target_root,args.version_name,ssh_target=args.ssh_target)


if __name__=='__main__':raise SystemExit(cli_result(main))
