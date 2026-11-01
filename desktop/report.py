# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Offline single-file report. Templates own language; astronomy stays in model."""
import json
import html
import re
from pathlib import Path
from string import Template
from datetime import datetime, timezone
from PySide6.QtCore import QBuffer,QByteArray,QIODevice,QSize,QRectF,QPointF
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgGenerator
from common import ROOT
from .model import ASPECTS,ASPECT_IDS,HOUSE_SYSTEMS,APP_VERSION,sorted_aspect_details
from .chart import paint_wheel
from .aspects import draw_symbol
from .zodiac import draw_zodiac
from .house_positions import validate_chart_houses

TEMPLATES=ROOT/'templates/report'

def page_counter_content(pattern):
    """Translate a footer without placing raw labels inside CSS string syntax."""
    if pattern.count('{page}')!=1 or pattern.count('{pages}')!=1:
        raise ValueError('page_number must contain {page} and {pages} exactly once')
    def quoted(value):
        value=value.replace('\\','\\\\').replace('"','\\"').replace('\n','\\a ').replace('\r','')
        return '"'+value.replace('<','\\3c ').replace('>','\\3e ')+'"'
    return ' '.join('counter(page)' if x=='{page}' else 'counter(pages)' if x=='{pages}' else quoted(x)
        for x in re.split(r'(\{page\}|\{pages\})',pattern) if x)
def available_templates():
    result=[]
    for folder in sorted(TEMPLATES.iterdir()):
        if folder.is_dir() and (folder/'report.html').is_file() and (folder/'labels.json').is_file():
            labels=json.loads((folder/'labels.json').read_text(encoding='utf-8'))
            result.append((folder,labels['template_name']))
    return sorted(result,key=lambda item:(item[0].name!='zh-TW',item[0].name))

def svg_image(width,height,paint):
    data=QByteArray();buffer=QBuffer(data);buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    svg=QSvgGenerator();svg.setOutputDevice(buffer);svg.setSize(QSize(width,height));svg.setViewBox(QRectF(0,0,width,height))
    painter=QPainter(svg)
    try:paint(painter)
    finally:painter.end();buffer.close()
    result=bytes(data).decode('utf-8')
    result=result[result.index('<svg'):]
    # Qt emits physical millimetres; HTML should size the responsive viewBox.
    return re.sub(r'\s(?:width|height)="[^"]*"','',result,count=2)

def render_html(chart,include_notes=False,template_dir=None):
    validate_chart_houses(chart)
    folder=Path(template_dir or TEMPLATES/'zh-TW')
    labels=json.loads((folder/'labels.json').read_text(encoding='utf-8'))
    esc=lambda value:html.escape(str(value),quote=True)
    def t(key,**values):return esc(labels[key].format(**values))
    def body(name):return esc(labels['bodies'][name])
    def zodiac(lon):
        total=round((lon%360)*3600)%(360*3600);sign,rest=divmod(total,108000)
        degree,rest=divmod(rest,3600);minute,second=divmod(rest,60)
        text=f'{esc(labels["signs"][sign])} {degree:02}°{minute:02}′{second:02}″'
        if not labels['lang'].startswith('en'):return text
        if sign not in zodiac_symbols:
            icon=svg_image(24,24,lambda p:draw_zodiac(p,sign,QPointF(12,12),20,'#47382e'))
            # Decorative outlines must not add Qt's document metadata to copied
            # table text; the adjacent name provides the accessible label.
            icon=re.sub(r'<(?:title|desc)>.*?</(?:title|desc)>','',icon,flags=re.S)
            icon=re.sub(r'>\s+<','><',icon).strip()
            zodiac_symbols[sign]=icon.replace('<svg','<svg class="zodiac-icon" aria-hidden="true" focusable="false"',1)
        return '<span class="zodiac-position">'+zodiac_symbols[sign]+'<span class="zodiac-text">'+text+'</span></span>'
    zodiac_symbols={}
    def table(headers,rows,cls=''):
        return f'<table class="{cls}"><thead><tr>'+''.join('<th scope="col">'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
    def symbol(angle):return svg_image(30,30,lambda p:draw_symbol(p,QRectF(0,0,30,30),angle))
    symbols={a:symbol(a) for a,_,_,_,_ in ASPECTS}
    active=[a for a in ASPECTS if not a[4] or chart['input']['minor_aspects']]
    legend='<div class="legend">'+''.join(
        '<div class="legend-item"><span class="swatch" style="border-top:2px '+('dotted' if minor else 'solid')+' '+color+'"></span>'+symbols[a]+
        f'<span>{a}° {esc(labels["aspects"][str(a)])}<small>±{chart["orbs"][a]:g}°</small></span></div>'
        for a,_,_,color,minor in active)+'</div>'
    b=chart['input']
    def coordinate(value,latitude=False):
        total=round(abs(value)*360000);d,rest=divmod(total,360000);m,s=divmod(rest,6000)
        direction=('north' if value>=0 else 'south') if latitude else ('east' if value>=0 else 'west')
        return f'{t(direction)} {d}°{m:02}′{s/100:05.2f}″ ({abs(value):.5f}°)'
    settings=[(t('name'),esc(b['name'] or labels['unnamed'])),(t('gender'),esc(labels['genders'][b['gender']])),
        (t('birth_time'),esc(b['local_iso'].replace('T',' '))),
        (t('longitude'),coordinate(b['longitude'])),(t('latitude'),coordinate(b['latitude'],True)),
        (t('timezone'),esc(b['zone'])),(t('offset'),esc(chart['utc_offset'])),
        (t('dst'),t('dst_value',minutes=chart['dst_minutes']) if chart['dst_minutes'] else t('dst_none')),
        (t('utc'),esc(datetime.fromisoformat(chart['utc']).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'))),
        (t('house_system'),esc(labels.get('house_systems',{}).get(b['system'],HOUSE_SYSTEMS[b['system']]))),
        (t('reference'),t('reference_value')),(t('node'),t('true_node')),
        (t('fortune'),t('day' if chart['day_chart'] else 'night')),
        (t('small_bodies'),t('shown' if b['small_bodies'] else 'hidden')),
        (t('minor_aspects'),t('shown' if b['minor_aspects'] else 'hidden')),
        (t('r_symbol'),t('r_meaning'))]
    if 'house_latitude' in b:
        settings.append((t('house_latitude'),t('enabled' if b['house_latitude'] else 'disabled')))
    def fields(rows,classes=''):
        return '<dl class="'+classes+'">'+''.join('<div'+(' class="house-latitude-setting"' if k==esc(labels.get('house_latitude','')) else '')+'><dt>'+k+'</dt><dd>'+v+'</dd></div>' for k,v in rows)+'</dl>'
    metadata='<div class="identity">'+fields(settings[:2],'identity-person')+fields(settings[2:3],'identity-birth')+'</div>'
    for key,rows in [('location_heading',settings[3:9]),('settings_heading',settings[9:])]:
        metadata+='<section class="meta-group"><h2>'+esc(labels.get(key,labels['timezone' if key=='location_heading' else 'house_system']))+'</h2>'+fields(rows,'meta-fields '+('settings-fields' if key=='settings_heading' else 'location-fields'))+'</section>'
    warnings='<ul class="warnings">'+''.join('<li>'+esc(labels['warnings'][note])+'</li>' for note in chart['notes'])+'</ul>' if chart['notes'] else ''
    from .help import has_azimuth_notice, has_aligned_azimuth_notice, article_html
    affected=has_azimuth_notice(chart)
    house_notice=('' if not affected else '<div class="house-notice" role="note">'+
        t('azimuth_aligned_notice' if has_aligned_azimuth_notice(chart) else 'azimuth_notice')+
        ' <a href="#azimuth-help">'+t('azimuth_read_more')+'</a></div>')
    help_locale='en-US' if labels['lang'].startswith('en') else 'zh-TW'
    azimuth_help=('' if not affected else '<section class="page help-article" id="azimuth-help">'+article_html(help_locale)+'</section>')
    localized=dict(chart,points=[dict(p,short=labels['shorts'][str(p['id'])]) for p in chart['points']])
    wheel=svg_image(1000,1000,lambda p:paint_wheel(p,localized,background='transparent',labels=labels))
    # Names remain accessible while the visible zodiac ring uses shared paths.
    wheel=wheel.replace('<svg','<svg role="img" aria-label="'+esc(labels['chart_title']+': '+', '.join(labels['signs']))+'"',1)
    positions=table([t('body'),t('position'),t('house'),t('motion')],[(body(p['name']),zodiac(p['lon']),str(p['house']) if p['house'] is not None else esc(labels.get('undefined_house','—')),t('retrograde') if p['retrograde'] else ('—' if p['speed'] is None else t('direct'))) for p in chart['points']])
    houses=table([t('house'),t('cusp')],[(t('house_number',number=i+1),zodiac(lon)) for i,lon in enumerate(chart['cusps'])])
    points=sorted((p for p in chart['points'] if p['id'] in ASPECT_IDS),key=lambda p:ASPECT_IDS.index(p['id']))
    lookup={frozenset((a['a'],a['b'])):a for a in chart['aspects']}
    matrix='<table class="matrix"><thead><tr><th></th>'+''.join('<th scope="col">'+esc(labels['shorts'][str(p['id'])])+'</th>' for p in points)+'</tr></thead><tbody>'
    for i,p in enumerate(points):
        matrix+='<tr><th scope="row">'+esc(labels['shorts'][str(p['id'])])+'</th>'
        for j,q in enumerate(points):
            a=lookup.get(frozenset((p['name'],q['name']))) if i>j else None
            desc=body(p['name'])+' × '+body(q['name'])
            if a:desc+=f' · {a["angle"]}° · '+t('deviation')+f' {a["orb"]:.3f}°'
            matrix+='<td class="'+('diagonal' if i==j else 'upper' if j>i else '')+'" title="'+desc+'">'+(symbols[a['angle']] if a else '')+'</td>'
        matrix+='</tr>'
    matrix+='</tbody></table>'
    details=table([t('body_a'),t('body_b'),t('aspect'),t('deviation'),t('orb')],[(body(a['a']),body(a['b']),f'{esc(labels["aspects"][str(a["angle"])])} {a["angle"]}°',f'{a["orb"]:.3f}°',f'{a["limit"]:g}°') for a in sorted_aspect_details(chart['aspects'])])
    if not chart['aspects']:details+='<p>'+t('no_aspects')+'</p>'
    notes='<section class="notes"><h3>'+t('notes')+'</h3><p>'+esc(b['notes'])+'</p></section>' if include_notes and b.get('notes') else ''
    css=(folder/'style.css').read_text(encoding='utf-8')
    css=css.replace('/* PAGE_NUMBER_CONTENT */',page_counter_content(labels['page_number']))
    context={key:esc(value) for key,value in labels.items() if isinstance(value,str)}
    context.update(css=css,font_css='',wheel=wheel,metadata=metadata,warnings=warnings,positions=positions,houses=houses,
        matrix=matrix,legend=legend,details=details,notes_content=notes,version=APP_VERSION,
        person=esc(b['name'] or labels['unnamed']),license='',house_notice=house_notice,
        azimuth_help=azimuth_help,chart_page_class='page has-house-notice' if affected else 'page')
    return Template((folder/'report.html').read_text(encoding='utf-8')).substitute(context)

def export_html(chart,path,include_notes=False,template_dir=None):
    content=render_html(chart,include_notes,template_dir)
    Path(path).write_text(content,encoding='utf-8')
