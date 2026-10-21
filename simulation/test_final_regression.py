# -*- coding: utf-8 -*-
"""最终综合回归：快速发展激活、民意页渲染、UX（切页不暂停/点建筑出详情）"""
from playwright.sync_api import sync_playwright

from pathlib import Path
_HERE = Path(__file__).resolve().parent
GAME = (_HERE.parent / 'index.html').as_uri()

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(GAME)
    page.wait_for_timeout(400)

    print('=== 回归1：快速发展（8住宅4农庄）→ 激活 + 民意页渲染 ===')
    page.evaluate("""()=>{
      newGame();
      const pi = S.terrain.findIndex(t=>t==='grass');
      S.cells[pi] = {kind:'b', type:'president', lv:1, upg:null};
      S.started = true; S.res.wood=99999; S.res.food=99999; S.res.iron=9999;
      let h=0,f=0;
      for (let i=0;i<S.cells.length;i++){
        if (S.cells[i] || S.terrain[i]!=='grass') continue;
        if (h<8){ S.cells[i]={kind:'b',type:'house',lv:1,workers:0,limit:0,upg:null,invested:{wood:20}}; h++; }
        else if (f<4){ S.cells[i]={kind:'b',type:'farm',lv:1,workers:0,limit:6,upg:null,invested:{wood:30}}; f++; }
      }
    }""")
    for i in range(40):
        if page.evaluate("()=>S.societyOn"): break
        page.evaluate("()=>nextYear()")
    st = page.evaluate("()=>({t:S.t,pop:Math.round(S.pop),on:S.societyOn,S:S.morale.farm.S,G:S.morale.farm.G})")
    print('  激活: 第 %d 年 | 人口 %d | 农场 S=%.1f G=%.1f' % (st['t'], st['pop'], st['S'], st['G']))
    page.evaluate("()=>{ S.page='morale'; render(); }")
    dom = page.evaluate("()=>document.getElementById('view').innerHTML")
    print('  民意页含行业表格:', '<table>' in dom, '| 含 S/G 表头:', 'S 短期情绪' in dom)
    print('  拓荒提示已消失:', '尚未形成社会' not in dom)

    print()
    print('=== 回归2：UX——切页面不暂停 + 点建筑出详情 ===')
    page.evaluate("()=>{ S.running = true; S.started = true; }")
    page.evaluate("()=>setPage('map')")
    paused = page.evaluate("()=>!S.running")
    print('  切页面后仍在运行(未暂停):', not paused)
    # 点一座已建成农庄 → 出详情页
    idx = page.evaluate("""()=>{ const l=builtList().find(x=>x.b.type==='farm'); return l?l.i:-1; }""")
    page.evaluate("(i)=>cellClick(i)", idx)
    det = page.evaluate("()=>({page:S.page, detail:S.detail})")
    print('  点农庄(格%d) → page=%s detail=%s' % (idx, det['page'], det['detail'] is not None))
    dom2 = page.evaluate("()=>document.getElementById('view').innerHTML")
    print('  详情页含升级信息:', '升级' in dom2, '| 含民意系数:', '民意系数' in dom2)
    page.evaluate("()=>{ S.running = false; }")

    print()
    print('=== 回归3：头部标签两态 ===')
    tag1 = page.evaluate("()=>document.getElementById('hYear').innerHTML")
    print('  定居期标签:', '民意已激活' in tag1)
    page.evaluate("()=>{ S.societyOn = false; render(); }")
    tag2 = page.evaluate("()=>document.getElementById('hYear').innerHTML")
    print('  拓荒期标签(含进度):', '形成社会' in tag2 and '/ 30' in tag2)
    page.evaluate("()=>{ S.societyOn = true; render(); }")

    print()
    print('JS 错误:', errors if errors else '无')
    browser.close()
