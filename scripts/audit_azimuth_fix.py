# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 OpenBirthChart contributors
"""One explicit migration audit: 0.6.0 -> directed Azimuth in 0.6.1.

Never skips cases or changes a baseline. Ordinary release checks still compare
every field exactly against the separately sealed 0.6.1 reference.
"""
import argparse
import copy
from pathlib import Path
from numerical_regression import ROOT,BASELINE,load_run,read,write,differences,verify_seal

def audit(candidate,output):
    verify_seal(BASELINE)
    bm,be,br=load_run(BASELINE);cm,ce,cr=load_run(candidate)
    old=read(BASELINE/'cases.json');new=read(Path(candidate)/'cases.json')
    allowed={c['id'] for c in old['cases'] if c['id'].startswith('edge-azimuth-')}
    assert len(allowed)==16
    expected=copy.deepcopy(old);expected['baseline_version']='0.6.1'
    for c in expected['cases']:
        if c['id'] in allowed:
            assert c['input']['system']=='H' and c['expected']=='UserError'
            c['expected']='ok'
    assert new==expected,'Input change beyond the 16 approved outcome transitions'
    assert not cm['unexpected_outcomes'] and not cm['guard_events']
    assert cm['contracts']==bm['contracts']
    assert be['dependencies']==ce['dependencies'] and be['data']==ce['data'] and be['locks']==ce['locks']
    transitions=[];unplanned=[];unchanged=0
    for ident in br:
        diff=list(differences(br[ident]['result'],cr[ident]['result']))
        if ident in allowed:
            assert br[ident]['result']['status']=='UserError'
            assert cr[ident]['result']['status']=='ok'
            chart=cr[ident]['raw']
            assert len(chart['cusps'])==12 and len(chart['all_points'])==20
            assert all(p['house'] in range(1,13) for p in chart['all_points'])
            transitions.append(dict(id=ident,before='UserError',after='ok'))
        elif diff:unplanned.extend(dict(case_id=ident,**d) for d in diff)
        else:unchanged+=1
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    summary=dict(passed=not unplanned and len(transitions)==16 and unchanged==1271,
        original_baseline='0.6.0',candidate_version=ce['app_version'],total=1287,
        unchanged_results=unchanged,approved_error_to_success=transitions,
        unexpected_changed_fields=len(unplanned),inputs_identical=True,
        dependencies_and_data_unchanged=True,old_cases_sha256=bm['cases_sha256'],new_cases_sha256=cm['cases_sha256'])
    write(output/'summary.json',summary);write(output/'unexpected-differences.json',unplanned)
    lines=['# 0.6.0 → 0.6.1 Azimuth 修復差異', '',
        f"1287 筆：{unchanged} 筆計算結果逐值完全不變；16 筆指定 Azimuth 由拒絕改為成功。",
        f"非預期欄位差異：{len(unplanned)}。",'',
        '所有輸入與次序不變。cases-v2.json 只更新基準版本標籤，以及這 16 筆的預期結果。',
        '套件、時間／星曆資料、lock 檔完全未變。舊案例與舊基準不覆寫。','']
    lines += [f"- {r['id']}: UserError → ok" for r in transitions]
    (output/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Migration audit:',summary['passed'],'unchanged:',unchanged,'expected fixes:',len(transitions),'unplanned fields:',len(unplanned))
    return 0 if summary['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raise SystemExit(audit(a.run,a.output))
