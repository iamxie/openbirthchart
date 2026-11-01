# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Static distribution audit. Findings are evidence, not a clean-room/legal proof."""
import ast
import importlib.metadata as md
from pathlib import Path
import re
import subprocess
from common import ROOT, dump, sha

def scan_python(path):
    text = path.read_text(encoding='utf-8-sig')
    tree = ast.parse(text)
    imports = []
    dynamic = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or '']
        else:
            names = []
        for name in names:
            if name.split('.')[0] in ('swisseph','pyswisseph','pysweph'):
                imports.append({'line':node.lineno,'module':name})
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module':
            dynamic.append({'line':node.lineno, 'expression':ast.unparse(node)})
    return imports, dynamic

def main():
    vendor=ROOT/'vendor/libephemeris'
    expected_commit='7c77b70717cf8420b85c19d3aaad128060998007'
    commit=subprocess.check_output(['git','-c',f'safe.directory={vendor.as_posix()}',
        '-C',str(vendor),'rev-parse','HEAD'],text=True).strip()
    if commit != expected_commit: raise RuntimeError(f'Unexpected source commit: {commit}')
    result = {'scope':'Installed core distributions; AST imports and dynamic-import call sites; source identity. Not a proof about all Git history or third-party copyright.',
              'distributions':[], 'direct_swiss_imports':[], 'dynamic_import_sites':[],
              'swiss_binary_or_data_files':[], 'source_inventory':[], 'libephemeris_source_mismatches':[]}
    for dist in sorted(md.distributions(),key=lambda d:d.metadata['Name'].lower()):
        result['distributions'].append({'name':dist.metadata['Name'],'version':dist.version,
                                       'requirements':dist.requires or []})
        for rel in dist.files or []:
            name = str(rel).replace('\\','/')
            path = Path(dist.locate_file(rel))
            if name.endswith('.se1') or re.search(r'(swisseph|sweph).*(\.pyd|\.dll|\.so)$',name,re.I):
                result['swiss_binary_or_data_files'].append(name)
            if path.suffix != '.py' or not path.is_file(): continue
            imports,dynamic = scan_python(path)
            for item in imports: result['direct_swiss_imports'].append(dict(item, distribution=dist.metadata['Name'],file=name))
            if name.startswith(('libephemeris/','kerykeion/')):
                result['source_inventory'].append({'file':name,'sha256':sha(path)})
                result['dynamic_import_sites'].extend(dict(item,file=name) for item in dynamic)
                if name.startswith('libephemeris/'):
                    source = ROOT/'vendor/libephemeris'/name
                    if not source.is_file(): raise RuntimeError(f'Missing audit source: {source}')
                    if source.exists() and sha(source) != sha(path):
                        # Git converts CRLF on Windows; compare normalized text as well.
                        if source.read_text(encoding='utf-8-sig') != path.read_text(encoding='utf-8-sig'):
                            result['libephemeris_source_mismatches'].append(name)
    result['source_checkout_commit'] = commit
    result['reviewed_paths'] = [
        {'path':'kerykeion/ephemeris_backend/backend.py','finding':'Optional Swiss dynamic branch exists. Forced KERYKEION_BACKEND=libephemeris fails if unavailable; benchmark blocks Swiss import.'},
        {'path':'libephemeris/planets.py','finding':'Skyfield/JPL path; absent planet-center SPK explicitly selects system barycenter.'},
        {'path':'libephemeris/net.py','finding':'Sealed network policy; benchmark additionally applies CPython audit hooks.'},
        {'path':'libephemeris/state.py','finding':'Explicit de440s.bsp selection; shared timescale from local Skyfield data.'},
    ]
    vendor=ROOT/'vendor/libephemeris'
    result['source_generation_scan']=[]
    for path in sorted((vendor/'scripts').glob('*.py')):
        imports,dynamic=scan_python(path)
        result['source_generation_scan'].append({'file':path.relative_to(vendor).as_posix(), 'sha256':sha(path),
                                                'swiss_imports':imports, 'dynamic_imports':dynamic})
    result['hard_dependency_pass'] = (not result['swiss_binary_or_data_files'] and not result['direct_swiss_imports'] and
        not any('swiss' in d['name'].lower() or 'pysweph' in d['name'].lower() for d in result['distributions']))
    result['source_audit_pass'] = (bool(result['source_generation_scan']) and not result['libephemeris_source_mismatches']
        and not any(row['swiss_imports'] for row in result['source_generation_scan']))
    dump(ROOT/'results/dependency-audit.json',result)
    print({key:len(result[key]) for key in ('source_inventory','direct_swiss_imports','swiss_binary_or_data_files','libephemeris_source_mismatches')})
    return 0 if result['hard_dependency_pass'] and result['source_audit_pass'] else 1

if __name__ == '__main__': raise SystemExit(main())
