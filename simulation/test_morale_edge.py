# -*- coding: utf-8 -*-
"""补充验证：limit=0 幻影缺员；S 回升过 75 的耗时"""
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

    def years(n): page.evaluate("(n)=>{ for(let i=0;i<n;i++) nextYear(); }", n)
    def snap(): return page.evaluate("""()=>({
      t:S.t, societyOn:S.societyOn, pop:Math.round(S.pop),
      farmG:S.morale.farm?S.morale.farm.G:null, farmS:S.morale.farm?S.morale.farm.S:null,
      debuff:Object.keys(S.debuff)
    })""")

    # ---------- 验证1：limit=0 停工不算缺员 ----------
    print('=== 验证1：农庄 limit=0 停工 → 无幻影缺员 ===')
    page.evaluate("""()=>{
      newGame();
      const pi = S.terrain.findIndex(t=>t==='grass');
      S.cells[pi] = {kind:'b', type:'president', lv:1, upg:null};
      S.started = true; S.res.wood=99999; S.res.food=99999;
      let houses=0, farms=0;
      for (let i=0;i<S.cells.length;i++){
        if (S.cells[i] || S.terrain[i]!=='grass') continue;
        if (houses<3){ S.cells[i]={kind:'b',type:'house',lv:1,workers:0,limit:0,upg:null,invested:{wood:20}}; houses++; }
        else if (farms<2){ S.cells[i]={kind:'b',type:'farm',lv:1,workers:0,limit:6,upg:null,invested:{wood:30}}; farms++; }
      }
    }""")
    for i in range(30):
        if page.evaluate("()=>S.societyOn"): break
        years(1)
    st = snap()
    print('  激活: 第 %d 年 人口 %d' % (st['t'], st['pop']))
    # 把第二座农庄停工：limit=0、撤人
    page.evaluate("""()=>{
      const farms = builtList().filter(x=>x.b.type==='farm');
      farms[1].b.limit = 0; farms[1].b.workers = 0;
    }""")
    years(20)
    st = snap()
    print('  停工20年后: 农场 G=%s S=%.1f debuff=%s' % (st['farmG'], st['farmS'] or 0, st['debuff'] or '无'))
    print('  预期: G=0（无幻影缺员）| 实际: %s' % ('✓ 通过' if (st['farmG'] or 0)==0 else '✗ 失败'))

    # ---------- 验证2：S 从低位回升越过 75 的耗时 ----------
    print()
    print('=== 验证2：S=55/G=40 管理良好 → S 越 75 耗时与 G 衰减启动 ===')
    page.evaluate("""()=>{
      S.morale.farm.G = 40; S.morale.farm.S = 55;
      // 恢复停工农庄的岗位（补员），保证 short≈0
      builtList().filter(x=>x.b.type==='farm').forEach(x=>{ x.b.limit = 6; });
      S.res.food = 9999;
    }""")
    cross = None
    for yr in range(12):
        years(1)
        st = snap()
        if cross is None and (st['farmS'] or 0) > 75: cross = st['t']
        if yr in (2,3,4,5,6,8,11):
            print('  第 %d 年: S=%.1f G=%s' % (st['t'], st['farmS'] or 0, round(st['farmG'] or 0,1)))
    print('  S 首次越过 75: 第 %s 年（构造后第 %s 年）' % (cross, (cross or 0)))
    print('  JS 错误:', errors if errors else '无')
    browser.close()
