# -*- coding: utf-8 -*-
"""数值审计实测：三种开局策略的 40 年经济/人口曲线"""
from playwright.sync_api import sync_playwright

from pathlib import Path
_HERE = Path(__file__).resolve().parent
GAME = (_HERE.parent / 'index.html').as_uri()

BASE = """
(strategy) => {
  newGame();
  const pi = S.terrain.findIndex(t=>t==='grass');
  S.cells[pi] = {kind:'b', type:'president', lv:1, upg:null};
  S.started = true;
  window.BUILT = 0;
  // 直接落成并扣材料（跳过工期，测稳态经济）
  window.tryBuild = (type) => {
    const cost = BUILD[type].cost;
    for (const r in cost) if ((S.res[r]||0) < cost[r]) return false;
    for (let i=0;i<S.cells.length;i++){
      if (S.cells[i]) continue;
      if (!BUILD[type].where.includes(S.terrain[i])) continue;
      pay(cost);
      S.cells[i] = {kind:'b', type, lv:1, workers:0, limit:BUILD[type].post, upg:null,
                    invested:Object.assign({},cost)};
      window.BUILT++;
      return true;
    }
    return false;
  };
  const plan = { balanced:['farm','lumber','house'], housefirst:['house','house','lumber'],
                 farmfirst:['farm','farm','lumber'] }[strategy];
  plan.forEach(t=>window.tryBuild(t));
  autoFill();
}
"""

# 理性玩家每年决策：粮不够→农庄；床位不足→住宅；有闲人→产建
STEP = """
() => {
  const pop = S.pop;
  const foodOut = ofType('farm').reduce((s,x)=>s+outputOf(x.b),0);
  const woodOut = ofType('lumber').reduce((s,x)=>s+outputOf(x.b),0);
  const spare = unemployed();
  // 优先级：粮 < 人口×1.5 → 农庄；空床 < 3 → 住宅；闲人 ≥ 5 → 伐木场/矿场
  if (foodOut < pop*1.5) window.tryBuild('farm');
  if (beds() - pop < 3) window.tryBuild('house');
  if (spare >= 5) (window.tryBuild('lumber') || window.tryBuild('farm'));
  nextYear();
  return {
    t:S.t, pop:Math.round(S.pop), beds:beds(),
    food:Math.round(S.res.food), wood:Math.round(S.res.wood),
    foodOut:+foodOut.toFixed(1), woodOut:+woodOut.toFixed(1),
    spare:unemployed(), soc:S.societyOn,
    farms:ofType('farm').length, houses:ofType('house').length, lum:ofType('lumber').length
  };
}
"""

def run(strategy, years=40, show=None):
    with sync_playwright() as p:
        b = p.chromium.launch(); page = b.new_page()
        errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
        page.goto(GAME); page.wait_for_timeout(300)
        page.evaluate(BASE, strategy)
        rows = [page.evaluate(STEP) for _ in range(years)]
        b.close()
        return rows, errs

for strat, label in [('balanced','均衡开局 农庄+伐木场+住宅(70木)'),
                     ('housefirst','住宅优先 2住宅+伐木场(60木)'),
                     ('farmfirst','农业优先 2农庄+伐木场(80木)')]:
    rows, errs = run(strat)
    soc_year = next((r['t'] for r in rows if r['soc']), None)
    print('=== %s ===' % label)
    print('  年  人口 床位  粮存 木存  粮产 木产 闲人  建筑(农/住/伐)')
    for r in rows:
        if r['t'] in (1,2,3,5,8,12,16,20,25,30,35,40):
            print('  %2d  %4d %4d %5d %5d %6.1f %5.1f %4d   %d/%d/%d' % (
                r['t'], r['pop'], r['beds'], r['food'], r['wood'],
                r['foodOut'], r['woodOut'], r['spare'], r['farms'], r['houses'], r['lum']))
    print('  → 达 30 人(定居期): 第 %s 年 | 40年后人口 %d | 建造总数 %s' % (
        soc_year or '未达成', rows[-1]['pop'], rows[-1]['farms']+rows[-1]['houses']+rows[-1]['lum']))
    print('  JS 错误:', errs if errs else '无')
    print()
