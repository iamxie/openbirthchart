# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Build portable help fragments from the single bilingual Markdown article."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from html.parser import HTMLParser
import html
import re
from PySide6.QtGui import QTextDocument, QGuiApplication

ROOT=Path(__file__).resolve().parents[1]


class CleanBody(HTMLParser):
    """Keep Qt's Markdown structure and links, drop editor-specific typography."""
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.in_body=False
    def handle_starttag(self,tag,attrs):
        if tag=='body':self.in_body=True;return
        if not self.in_body:return
        attrs=dict(attrs);kept=''
        if tag=='a' and 'href' in attrs:kept=' href="'+html.escape(attrs['href'],quote=True)+'"'
        if tag=='span' and 'font-weight:700' in attrs.get('style',''):kept=' style="font-weight:700"'
        self.parts.append('<'+tag+kept+'>')
    def handle_endtag(self,tag):
        if tag=='body':self.in_body=False;return
        if self.in_body:self.parts.append('</'+tag+'>')
    def handle_data(self,data):
        if self.in_body:self.parts.append(html.escape(data))


def build():
    app=QGuiApplication.instance() or QGuiApplication([])
    source=(ROOT/'docs/azimuth.md').read_text(encoding='utf-8')
    pieces=re.split(r'<!-- language:(zh-TW|en-US) -->',source)
    assert len(pieces)==5
    for locale,markdown in zip(pieces[1::2],pieces[2::2]):
        doc=QTextDocument();doc.setMarkdown(markdown)
        parser=CleanBody();parser.feed(doc.toHtml())
        (ROOT/'docs'/('azimuth-'+locale+'.html')).write_text(''.join(parser.parts)+'\n',encoding='utf-8')
        print('Built Azimuth help:',locale)


if __name__=='__main__':build()
