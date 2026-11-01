# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Build an explicit public tree and complete source ZIP; never upload."""
import argparse,hashlib,json,re,shutil,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from desktop.model import APP_VERSION

ROOT_FILES=('README.md','README.en.md','LICENSE','NOTICE.md','LICENSING.md','THIRD_PARTY_DESKTOP.md',
    'DESKTOP_README.md','.gitignore','desktop_app.py','EphemerisDesktop.spec','third-party-sources.lock.json',
    'data-sources.lock.json','desktop-data-sources.lock.json','time-data-sources.lock.json',
    'observation-data-sources.lock.json','cases.json','utc-cases.json','sensitivity-cases.json')
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def public_paths():
    found={ROOT/p for p in ROOT_FILES}
    found.update(ROOT.glob('*.ps1'))
    for name in ('desktop','scripts','tests','requirements','templates','translations','docs','config','licenses'):
        found.update(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    found.update((ROOT/'data/desktop/theme').glob('*.svg'))
    # Keep the small OFL icon font and its original license in Git. Its upstream
    # download can reject automated requests; these bytes remain hash-locked.
    for name in ('Astronomicon.ttf','OFL-License.txt'):
        found.add(ROOT/'data/desktop/astronomicon'/name)
    found.update((ROOT/'regression').glob('*current.json'))
    found.update((ROOT/'regression').glob('*/cases*.json'))
    found.update(evidence_paths())
    for path in found:
        if not path.is_file():raise ValueError('Required public source missing: '+str(path))
    return sorted(found)
def scan_public(paths):
    failures=[]
    for p in paths:
        rel=p.relative_to(ROOT).as_posix()
        if p.suffix.lower() in ('.sqlite','.db','.pem','.key','.pfx') or p.name.startswith('.env'):
            failures.append(rel+': private-file type')
        if p.suffix.lower() in ('.py','.ps1','.md','.json','.in','.lock','.toml','.txt','.spec'):
            content=p.read_text(encoding='utf-8',errors='replace')
            for pattern in (r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{40,}'):
                if re.search(pattern,content):failures.append(rel+': credential pattern')
    if failures:raise ValueError('\n'.join(failures))
def evidence_paths():
    """Keep local article evidence links without publishing unrelated task logs."""
    pending=list((ROOT/'docs').glob('*.md'));seen=set();extra=set()
    while pending:
        p=pending.pop()
        if p in seen:continue
        seen.add(p)
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if link.startswith(('http:','https:','#','mailto:')):continue
            q=(p.parent/link.split('#')[0]).resolve()
            if not q.is_relative_to(ROOT) or not q.is_file():continue
            rel=q.relative_to(ROOT)
            if rel.parts[0] not in ('results','regression'):continue
            if q.suffix.lower() in ('.sqlite','.db','.ps1','.py','.zip'):continue
            extra.add(q)
            if q.suffix=='.md':pending.append(q)
    return extra
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--upstream',type=Path,required=True)
    parser.add_argument('--reviewed-reference',type=Path,required=True);args=parser.parse_args()
    paths=public_paths();scan_public(paths)
    public=ROOT/'dist'/f'OpenBirthChart-{APP_VERSION}-public-source'
    if (public/'.git').exists():raise ValueError('Refusing to overwrite a working Git repository')
    public.mkdir(parents=True,exist_ok=True)
    inventory=[]
    for path in paths:
        rel=path.relative_to(ROOT);target=public/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        inventory.append(dict(path=rel.as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
    (public/'PUBLIC-SOURCE-MANIFEST.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    mapping={p.relative_to(ROOT).as_posix():p for p in paths}
    for group in ('regression','data/core','data/time','data/desktop'):
        for p in (ROOT/group).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:mapping[p.relative_to(ROOT).as_posix()]=p
    for p in evidence_paths():mapping[p.relative_to(ROOT).as_posix()]=p
    reference=args.reviewed_reference.resolve()
    for p in reference.rglob('*'):
        if p.is_file():mapping['validation/reviewed/'+p.relative_to(reference).as_posix()]=p
    sources=json.loads((ROOT/'third-party-sources.lock.json').read_text(encoding='utf-8'))
    for row in sources['archives']:
        p=args.upstream/row['filename']
        if not p.is_file() or sha(p)!=row['sha256']:raise ValueError('Upstream source mismatch: '+str(p))
        mapping['third_party/sources/'+row['filename']]=p
    # Only immutable numerical evidence is added, never smoke databases, logs,
    # local account configuration, virtual environments or private task notes.
    for rel,p in mapping.items():
        if p.suffix.lower() in ('.sqlite','.db','.pem','.key','.pfx') or p.name.startswith('.env'):raise ValueError('Private file in source archive: '+rel)
    prefix=f'OpenBirthChart-{APP_VERSION}-source';archive=ROOT/'dist'/(prefix+'.zip')
    entries=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for rel,path in sorted(mapping.items()):
            bundle.write(path,prefix+'/'+rel);entries.append(dict(path=rel,bytes=path.stat().st_size,sha256=sha(path)))
        bundle.writestr(prefix+'/SOURCE-MANIFEST.json',json.dumps(entries,indent=2))
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:raise ValueError('Source ZIP integrity failed')
    digest=sha(archive);archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    result=dict(version=APP_VERSION,public_tree=str(public),public_files=len(inventory),source_files=len(entries),
        source_zip=str(archive),bytes=archive.stat().st_size,sha256=digest,uploaded=False,
        content_policy='Explicit application allowlist; immutable regression and selected article evidence; no personal databases or keys',
        privacy_scan='Path exclusions and key-pattern scan; fixtures are synthetic; not a general security audit')
    out=ROOT/'results/desktop'/f'public-source-checks-{APP_VERSION}.json';out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
