# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Extract marked messages, preserve TS translations, validate and compile Qt QM.

Run with --update to add newly marked sources for translators; normal builds
reject missing/unfinished translations and mismatched format placeholders.
"""
import argparse
import ast
from pathlib import Path
import string
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'translations/desktop_en_US.ts'


def sources():
    found={}
    for path in sorted((ROOT/'desktop').glob('*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node,ast.Call) and node.args:
                name=node.func.id if isinstance(node.func,ast.Name) else ''
                if name not in ('tr','UserError'):continue
                source=node.args[0]
                if isinstance(source,ast.Constant) and isinstance(source.value,str):
                    found.setdefault(source.value,(path.relative_to(ROOT).as_posix(),node.lineno))
    # Canonical domain values are translated only at presentation boundaries.
    for path in (ROOT/'desktop/model.py',ROOT/'desktop/window.py',ROOT/'desktop/errors.py',ROOT/'desktop/storage.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and any('\u3400'<=c<='\u9fff' for c in node.value):
                found.setdefault(node.value,(path.relative_to(ROOT).as_posix(),node.lineno))
    return found


def fields(value):
    return sorted((field,fmt,conv) for _,field,fmt,conv in string.Formatter().parse(value) if field is not None)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--update',action='store_true');args=parser.parse_args()
    tree=ET.parse(CATALOG);root=tree.getroot();context=root.find('context')
    existing={m.findtext('source'):m for m in context.findall('message')};missing=[]
    for source,(filename,line) in sources().items():
        if source not in existing:
            if not args.update:missing.append(source);continue
            m=ET.SubElement(context,'message');ET.SubElement(m,'source').text=source
            ET.SubElement(m,'translation',type='unfinished');existing[source]=m
        m=existing[source]
        for location in m.findall('location'):m.remove(location)
        ET.SubElement(m,'location',filename='../'+filename,line=str(line))
    if args.update:
        ET.indent(tree);tree.write(CATALOG,encoding='utf-8',xml_declaration=True)
        print('Updated catalog; translate unfinished entries before building.');return
    for ctx in root.findall('context'):
        for m in ctx.findall('message'):
            source=m.findtext('source');translation=m.find('translation')
            if translation is None or translation.get('type')=='unfinished' or not translation.text:
                missing.append(source)
            elif fields(source)!=fields(translation.text):raise ValueError('Placeholder mismatch: '+source)
    if missing:raise ValueError('Missing translations:\n'+'\n'.join(missing))
    import PySide6
    # Call the bundled binary directly; venv entry points may retain old paths.
    tool=Path(PySide6.__file__).parent/('lrelease.exe' if sys.platform=='win32' else 'lrelease')
    subprocess.run([str(tool),str(CATALOG),'-qm',str(CATALOG.with_suffix('.qm'))],check=True)


if __name__=='__main__':main()
