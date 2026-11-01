# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Standalone multilingual timeline report and shared event detail markup."""
import html
import json
from pathlib import Path
from string import Template
from .report import TEMPLATES, available_templates, page_counter_content
from .timeline import BODY_NAMES, ANGLES
from .timeline_details import event_spans, sign_at, sign_path, overlapping_events, local_time
from .model import APP_VERSION

from .timeline_palette import COLORS
esc=lambda value:html.escape(str(value),quote=True)


def timeline_templates():
    return [(p,label) for p,label in available_templates() if all((p/name).is_file()
        for name in ('timeline.html','timeline.css','timeline-labels.json'))]


def labels_for(folder=None):
    folder=Path(folder or TEMPLATES/'zh-TW')
    labels=json.loads((folder/'labels.json').read_text(encoding='utf-8'))
    labels.update(json.loads((folder/'timeline-labels.json').read_text(encoding='utf-8')))
    return labels


def color_legend(labels):
    entries=[(None,labels['retro_legend'])]+[(a,labels['aspect_meanings'][str(a)]) for a in ANGLES]
    return '　 '.join(f'<span style="color:{COLORS[a]}">■</span> '+esc(text) for a,text in entries)


def event_title(event,labels):
    body=lambda b:labels['bodies'][BODY_NAMES[b]]
    return (labels['retro'].format(body=body(event.a)) if event.b is None else
        f'{body(event.a)} {event.angle}° {body(event.b)}')


def sign_name(sign,labels):
    return labels['unknown'] if sign is None else labels['signs'][sign]


def sign_description(result,event,labels,stamp=None):
    parts=[]
    for b in ((event.a,) if event.b is None else (event.a,event.b)):
        signs=sign_path(result,event,b) if stamp is None else [sign_at(result,b,stamp)]
        parts.append(labels['bodies'][BODY_NAMES[b]]+': '+' → '.join(sign_name(s,labels) for s in signs))
    return ' · '.join(parts)


def table(headers,rows):
    return '<table><thead><tr>'+''.join('<th scope="col">'+esc(h)+'</th>' for h in headers)+\
        '</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+cell+'</td>' for cell in row)+'</tr>' for row in rows)+'</tbody></table>'


def event_html(result,event,labels,compact=False):
    """HTML fragment usable by QTextBrowser and exported documents."""
    clock=lambda t:esc(local_time(t,result.request.zone))
    out=f'<h2 style="color:{COLORS[event.angle]}">'+esc(event_title(event,labels))+'</h2><p>'+clock(event.start)+' — '+clock(event.end)+'</p>'
    if event.angle is not None:
        out+='<p>'+esc(labels['aspect_meanings'][str(event.angle)])+'</p>'
        out+='<p>'+esc(labels['orb'].format(orb=result.request.orbs[ANGLES.index(event.angle)]))+'</p>'
    for clipped,key in ((event.clipped_start,'clipped_start'),(event.clipped_end,'clipped_end')):
        if clipped:out+='<p>'+esc(labels[key])+'</p>'
    if not compact:out+='<h3>'+esc(labels['history'])+'</h3><p>'+esc(labels['history_hint'])+'</p>'
    bodies=(event.a,) if event.b is None else (event.a,event.b)
    out+=table([labels['start'],labels['end'],*[labels['bodies'][BODY_NAMES[b]] for b in bodies]],
        [[clock(a),clock(b),*[esc(sign_name(s,labels)) for s in signs]] for a,b,signs in event_spans(result,event)])
    if event.kind=='aspect':
        out+='<h3>'+esc(labels['exact'].format(n=len(event.exact)))+'</h3>'
        out+=table([labels['time'],labels['signs_heading']],[[clock(t),esc(sign_description(result,event,labels,t))] for t in event.exact]) if event.exact else '<p>'+esc(labels['no_exact'])+'</p>'
    return out


def overlaps_html(result,event,labels,stamp=None,scheme='#event-'):
    rows=[]
    for index,other,left,right in overlapping_events(result,event,stamp):
        rows.append([f'<a href="{scheme}{index}">{esc(event_title(other,labels))}</a>',
            esc(local_time(left,result.request.zone)),esc(local_time(right,result.request.zone)),
            esc(sign_description(result,other,labels,stamp) if stamp is not None else
                sign_description(result,type(other)(other.kind,other.a,other.b,other.angle,left,right),labels))])
    return '<p>'+esc(labels['overlap_hint'])+'</p>'+ (table(
        [labels['event'],labels['overlap_start'],labels['overlap_end'],labels['signs_heading']],rows)
        if rows else '<p>'+esc(labels['no_overlap'])+'</p>')


def gantt_pages(result,events,labels,window=None):
    """Bounded SVG pages: 30 elapsed days and 12 occupied lanes per page."""
    groups={}
    for index,event in events:groups.setdefault(event.key,[]).append((index,event))
    start,stop=window or (result.start,result.end)
    stop=max(stop,start+60)
    pages=[]
    while start<stop:
        end=min(stop,start+30*86400)
        lanes=[rows for rows in groups.values() if any(e.start<=end and e.end>=start for _,e in rows)]
        for offset in range(0,len(lanes),12):
            part=lanes[offset:offset+12];width=1100;height=40+len(part)*48
            x=lambda stamp:210+870*(stamp-start)/(end-start)
            svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(labels["timeline_title"])}">']
            for i in range(6):
                stamp=start+(end-start)*i/5;xx=x(stamp)
                date=local_time(stamp,result.request.zone,False)[5:16]
                svg.append(f'<text x="{xx:.2f}" y="17" text-anchor="{("end" if i==5 else "start")}" font-size="12">{esc(date)}</text><path d="M {xx:.2f} 26 V {height}" stroke="#ded3c6"/>')
            for row,items in enumerate(part):
                y=30+row*48
                svg.append(f'<text x="4" y="{y+24}" font-size="14">{esc(event_title(items[0][1],labels))}</text>')
                for index,event in items:
                    if event.end<start or event.start>end:continue
                    left,right=x(max(start,event.start)),x(min(end,event.end))
                    color=COLORS[event.angle]
                    svg.append(f'<a href="#event-{index}"><title>{esc(sign_description(result,event,labels))}</title><rect x="{left:.3f}" y="{y}" width="{max(2,right-left):.3f}" height="36" rx="3" fill="{color}"/>')
                    for lo,hi,signs in event_spans(result,event):
                        if hi<start or lo>end:continue
                        l,r=x(max(lo,start)),x(min(hi,end))
                        if event.start<lo<event.end and start<lo<end:svg.append(f'<path d="M {l:.3f} {y} v 36" stroke="white" stroke-dasharray="3 2"/>')
                        for j,sign in enumerate(signs):
                            text=sign_name(sign,labels)
                            # Full names only where legible; every interval is in the text catalog.
                            if r-l>max(34,len(text)*7+8):svg.append(f'<text x="{(l+r)/2:.3f}" y="{y+14+j*16}" fill="white" text-anchor="middle" font-size="12">{esc(text)}</text>')
                    for stamp in event.exact:
                        if start<=stamp<=end:
                            xx=x(stamp);svg.append(f'<path d="M {xx:.3f} {y-4} l 4 4 -4 4 -4 -4 Z" fill="{color}" stroke="white"/>')
                    svg.append('</a>')
            svg.append('</svg>')
            pages.append('<section class="page timeline-chart"><h2>'+esc(labels['timeline_title'])+'</h2><p>'+esc(local_time(start,result.request.zone))+' — '+esc(local_time(min(end,result.end),result.request.zone))+' · '+esc(result.request.zone)+'</p>'+''.join(svg)+'<p class="hint">'+color_legend(labels)+'</p><p class="hint">'+esc(labels['legend'])+'</p></section>')
        start=end
    return ''.join(pages)


def render_timeline_html(result,template_dir=None,selected=None):
    folder=Path(template_dir or TEMPLATES/'zh-TW');labels=labels_for(folder)
    events=list(enumerate(result.events))
    if selected is not None:events=[(i,e) for i,e in events if e is selected]
    intro='<h1>'+esc(labels['overview_title'])+'</h1><p>'+esc(local_time(result.start,result.request.zone))+' — '+esc(local_time(result.end,result.request.zone))+'</p><p>'+esc(result.request.zone)+'</p>'
    intro+='<p>'+esc(labels['body_scope'])+'</p>'
    intro+='<p>'+esc(labels['selected_scope'] if selected else labels['all_scope'])+'</p><p>'+esc(labels['convention'])+'</p>'
    intro+='<p>'+esc(labels['orbs'])+': '+esc(' · '.join(f'{a}° ±{o}°' for a,o in zip(ANGLES,result.request.orbs)))+'</p>'
    intro+='<p>'+esc(labels['print_hint'])+'</p>'
    intro+='<p>'+esc(labels['history_hint'])+'</p>'
    for note in result.notes:intro+='<p>'+esc(labels.get('warnings',{}).get(note,note))+'</p>'
    intro+=table([labels['event'],labels['start'],labels['end'],labels['signs_heading']],
        [[f'<a href="#event-{i}">{esc(event_title(e,labels))}</a>',esc(local_time(e.start,result.request.zone)),
          esc(local_time(e.end,result.request.zone)),esc(sign_description(result,e,labels))] for i,e in events])
    if not events:intro+='<p>'+esc(labels['no_events'])+'</p>'
    charts=gantt_pages(result,events,labels,(selected.start,selected.end) if selected is not None else None)
    if not charts:charts='<section class="page timeline-chart"><h2>'+esc(labels['timeline_title'])+'</h2><p>'+esc(labels['no_events'])+'</p></section>'
    content=charts.replace('<section ', '<section id="timeline" ',1)
    content+='<section class="page" id="overview">'+intro+'</section>'
    content+='<section class="page"><h1>'+esc(labels['details_title'])+'</h1>'
    for index,event in events:
        content+=f'<article id="event-{index}">'+event_html(result,event,labels,compact=True)
        if selected is not None:
            # Selected-event documents include other overlapping events as plain text,
            # since their full detail sections are outside the export scope.
            import re
            overlap=re.sub(r'<a href="[^"]*">(.*?)</a>',r'\1',overlaps_html(result,event,labels))
            content+='<h3>'+esc(labels['concurrent'])+'</h3>'+overlap
        content+='</article>'
    content+='</section>'
    css=(folder/'style.css').read_text(encoding='utf-8')+'\n'+(folder/'timeline.css').read_text(encoding='utf-8')
    css=css.replace('/* PAGE_NUMBER_CONTENT */',page_counter_content(labels['page_number']))
    return Template((folder/'timeline.html').read_text(encoding='utf-8')).substitute(
        lang=esc(labels['lang']),title=esc(labels['timeline_title']),css=css,content=content,
        overview=esc(labels['overview']),version=esc(APP_VERSION))


def export_timeline_html(result,path,template_dir=None,selected=None):
    Path(path).write_text(render_timeline_html(result,template_dir,selected),encoding='utf-8')
