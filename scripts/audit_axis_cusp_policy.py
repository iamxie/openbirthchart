# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""Audit the approved 0.6.3 -> 0.6.4 migration; never alter either baseline."""
import argparse, copy, json, math
from pathlib import Path
from collections import Counter
import numerical_regression as nr

ROOT=Path(__file__).resolve().parents[1]


def invariant(chart):
    c=copy.deepcopy(chart)
    for key in ('version','house_policy','house_notices'):c.pop(key,None)
    for key in ('all_points','points'):
        for p in c[key]:p.pop('house')
    for a in c['house_positions'].values():
        for key in ('policy','position','house','correction','boundary_correction'):a.pop(key,None)
    return nr.exact(c)


def audit(run,output,protected):
    oldfolder=ROOT/'regression/baselines/0.6.3';nr.verify_seal(oldfolder)
    om,oe,old=nr.load_run(oldfolder);nm,ne,new=nr.load_run(run)
    assert set(old)==set(new)
    assert not nm['unexpected_outcomes'] and not nm['guard_events']
    assert nm['outcomes']==om['outcomes']
    assert (oldfolder/'cases.json').read_bytes()==(run/'cases.json').read_bytes()
    for key in ('locks','data','dependencies'):assert oe[key]==ne[key],key
    protected_hashes=nr.read(protected)
    # The navigation README is maintained for the new baseline; numerical data,
    # archived validation reports, locks and reference files are immutable.
    documentation_updates=[]
    for p,digest in protected_hashes.items():
        current=nr.sha(ROOT/p)
        if Path(p).as_posix()=='regression/README.md' and current!=digest:
            documentation_updates.append(dict(path=p,before_sha256=digest,after_sha256=current))
        else:assert current==digest,p
    expected_pairs=nr.read(ROOT/'tests/fixtures/axis-cusp-0.6.3.json')['cases']
    expected={(p['case'],p['point_id']) for p in expected_pairs if p['expected_correction']}
    changed=[];notices=[];api_values=0;main_api=0
    for ident,row in new.items():
        a=old[ident]['raw'];b=row['raw'];main=ident.startswith('main-')
        if not isinstance(a,dict) or 'house_positions' not in a:
            assert nr.exact(a)==nr.exact(b),ident;continue
        assert invariant(a)==invariant(b),('non-placement value changed',ident)
        points={p['id']:p for p in b['all_points']}
        for p in a['all_points']:
            q=points[p['id']];key=str(p['id']);oa=a['house_positions'][key];na=b['house_positions'][key]
            api_values+=1;main_api+=int(main)
            assert oa['raw_position']==na['raw_position'] and oa['arguments']==na['arguments']
            assert na['house']==q['house']
            if p['house']!=q['house']:
                assert p['id'] in (-2,-3)
                assert na['correction']=='axis_cusp_roundoff'
                target=1 if p['id']==-2 else 10
                assert q['house']==target and na['position']==float(target)
                changed.append(dict(case=ident,group='main' if main else 'boundary',point_id=p['id'],name=p['name'],
                    system=b['input']['system'],before=p['house'],after=q['house'],raw_position=na['raw_position'],
                    correction=na['boundary_correction']))
            else:
                assert na['position']==oa['position'] and na['correction']==oa['correction'],(ident,key)
        if b['house_notices']:
            assert b['input']['system']=='H'
            notices.append(dict(case=ident,group='main' if main else 'boundary',input=b['input'],notices=b['house_notices']))
    main_changes=[r for r in changed if r['group']=='main']
    assert {(r['case'],r['point_id']) for r in main_changes}==expected
    assert len(main_changes)==223 and len({r['case'] for r in main_changes})==209
    assert main_api==24000
    assert Counter(r['group'] for r in notices)=={'main':42,'boundary':16}
    summary=dict(passed=True,version=ne['app_version'],cases=len(new),main_cases=1200,boundary_cases=87,
        main_changed_charts=len({r['case'] for r in main_changes}),main_changed_points=len(main_changes),
        main_unchanged_house_charts=1200-len({r['case'] for r in main_changes}),
        boundary_changed_charts=len({r['case'] for r in changed if r['group']=='boundary'}),
        boundary_changed_points=sum(r['group']=='boundary' for r in changed),
        main_by_point=dict(Counter(r['name'] for r in main_changes)),main_by_system=dict(Counter(r['system'] for r in main_changes)),
        notices=dict(Counter(r['group'] for r in notices)),raw_api_values_exactly_unchanged=api_values,
        main_raw_api_values_exactly_unchanged=main_api,all_non_placement_values_exactly_unchanged=True,
        protected_files_unchanged=len(protected_hashes)-len(documentation_updates),documentation_updates=documentation_updates,
        dependencies_and_data_unchanged=True,
        old_manifest_sha256=nr.sha(oldfolder/'manifest.json'),new_manifest_sha256=nr.sha(run/'manifest.json'))
    output.mkdir(parents=True,exist_ok=False)
    nr.write(output/'summary.json',summary);nr.write(output/'changes.json',changed);nr.write(output/'azimuth-notices.json',notices)
    lines=['# 0.6.4 ASC／MC 宮界補正與 Azimuth 提示：遷移稽核','',
        '從原始出生條件重新計算 1200 個固定案例及 87 個邊界案例；不複製舊回傳當作重算結果。','',
        f"- 主案例：209 張／223 個宮號變更；其餘 991 張宮號不變。ASC 141 個由 12 改為 1；MC 82 個由 9 改為 10。",
        f"- 額外邊界案例：{summary['boundary_changed_charts']} 張／{summary['boundary_changed_points']} 個宮號變更，逐筆見 changes.json。",
        '- 24000 個主案例原始 house_pos 回傳及所有呼叫參數逐值完全不變；所有非歸宮數值亦完全不變。',
        '- Azimuth 提示：主案例 42 張、額外反向邊界案例 16 張；未修正已知六宮編號差。',
        f"- 原有 {summary['protected_files_unchanged']} 個保護檔案（含基準／Swiss 對照／封存與鎖檔）SHA-256 均未變；套件及星曆亦未變。",
        '- 導覽 README 若更新至 0.6.4，另列修改前後雜湊；不將它算作未變檔案，也不豁免任何基準數據。',
        '- 原始回傳與補正後 position／house 分開保存，附 axis_cusp_roundoff 原因及宮頭身分／容差證據。',
        '- 這是版本間變動稽核；Swiss 外部對照另見 ../swiss-comparison/REPORT.md，不能將通過稽核解讀為已修復 Azimuth。','']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--protected',type=Path,default=ROOT/'results/numerical/release-0.6.4/protected-before.json')
    a=p.parse_args();audit(a.run,a.output,a.protected)
