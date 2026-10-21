# -*- coding: utf-8 -*-
"""民意系统有机验证：真缺员→积怨→事件；修复后→衰减→平息"""
from playwright.sync_api import sync_playwright

from pathlib import Path
_HERE = Path(__file__).resolve().parent
GAME = (_HERE.parent / 'index.html').as_uri()

SETUP = """
() => {
  newGame();
  const pi = S.terrain.findIndex(t=>t==='grass');
  S.cells[pi] = {kind:'b', type:'president', lv:1, upg:null};
  S.started = true;
  S.res.wood = 99999; S.res.food = 99999; S.res.iron = 9999; S.res.coal = 9999;
  const place = (type, n) => {
    let placed = 0;
    for (let i=0;i<S.cells.length && placed<n;i++){
      if (S.cells[i]) continue;
      if (!BUILD[type].where.includes(S.terrain[i])) continue;
      S.cells[i] = {kind:'b', type, lv:1, workers:0, limit:BUILD[type].post, upg:null,
                    invested:Object.assign({},BUILD[type].cost)};
      placed++;
    }
    return placed;
  };
  return {houses: place('house',3), farms: place('farm',4)};
}
"""

def run_years(page, n):
    return page.evaluate("(n)=>{ for(let i=0;i<n;i++) nextYear(); }", n)

def state(page):
    return page.evaluate("""()=>({
      t:S.t, pop:Math.round(S.pop), societyOn:S.societyOn,
      farmG:S.morale.farm?S.morale.farm.G:null, farmS:S.morale.farm?S.morale.farm.S:null,
      debuff:Object.keys(S.debuff), cd:S.cd,
      food:Math.round(S.res.food),
      farmPosts:(()=>{let w=0,h=0;builtList().filter(x=>x.b.type==='farm').forEach(x=>{w+=x.b.workers;h+=Math.min(x.b.limit||posts(x.b),posts(x.b));});return {w,h};})(),
      logTail:S.log.slice(-4)
    })""")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(GAME)
    page.wait_for_timeout(400)

    # ---------- 场景A：真缺员（3 住宅锁人口 + 每年增建农庄） ----------
    print('=== 场景A：人口锁死 + 每年+1 农庄（真缺员积怨） ===')
    print('  初始布置:', page.evaluate(SETUP))
    # 跑到民意激活
    for i in range(80):
        if page.evaluate("()=>S.societyOn"): break
        run_years(page, 1)
    st = state(page)
    print('  激活: 第 %d 年 | 人口 %d | 初始 G=%s' % (st['t'], st['pop'], st['farmG']))

    # 激活后：每年手动增建 1 座农庄（直接落成，模拟玩家持续扩张生产、人手跟不上）
    first_event_year = None
    maxG = 0
    for yr in range(45):
        page.evaluate("""()=>{
          for (let i=0;i<S.cells.length;i++){
            if (S.cells[i]) continue;
            if (!BUILD.farm.where.includes(S.terrain[i])) continue;
            S.cells[i] = {kind:'b', type:'farm', lv:1, workers:0, limit:6, upg:null,
                          invested:{wood:30}};
            break;
          }
        }""")
        run_years(page, 1)
        st = state(page)
        if st['farmG'] is not None: maxG = max(maxG, st['farmG'])
        if st['debuff'] and first_event_year is None:
            first_event_year = st['t']
            print('  ★ 第 %d 年首次行业事件！debuff=%s | 农场 G=%s S=%s' % (
                st['t'], st['debuff'], round(st['farmG'] or 0,1), round(st['farmS'] or 0,1)))
            print('    日志尾:', [l[:42] for l in st['logTail']])
    st = state(page)
    print('  45 年扩张后: 人口 %d | 农场岗 %d/%d (缺员 %.0f%%) | G 峰值 %.0f | 事件年份 %s | debuff=%s' % (
        st['pop'], st['farmPosts']['w'], st['farmPosts']['h'],
        100*(1-st['farmPosts']['w']/max(1,st['farmPosts']['h'])), maxG,
        first_event_year or '无', st['debuff']))
    print('  JS 错误:', errors if errors else '无')

    # ---------- 场景B：修复后积怨衰减（只留6座农庄，岗位基本补足） ----------
    print()
    print('=== 场景B：管理良好后 S 回升、G 衰减、事件平息 ===')
    # 直接构造：拆掉多余农庄（留6座=36岗，在岗39人→缺员率≈0），G 置 50，S 置 80
    page.evaluate("""()=>{
      let kept = 0;
      for (let i=0;i<S.cells.length;i++){
        const c = S.cells[i];
        if (c && c.kind==='b' && c.type==='farm'){
          if (kept < 6) kept++; else S.cells[i] = null;
        }
      }
      S.morale.farm.G = 50; S.morale.farm.S = 80;
      S.res.food = 9999; S.cd = 0;
    }""")
    g_track, events_after_calm, calm_year = [], [], None
    for yr in range(35):
        run_years(page, 1)
        st = state(page)
        g_track.append(round(st['farmG'] or 0))
        if st['debuff']:
            if calm_year is not None: events_after_calm.append(st['t'])
        if calm_year is None and (st['farmG'] or 0) < 30:
            calm_year = st['t']
    st = state(page)
    print('  G 轨迹(每5年):', g_track[::5])
    print('  S 现值: %.1f | G 现值: %.0f' % (st['farmS'] or 0, st['farmG'] or 0))
    print('  G 首次跌破 30: 第 %s 年 | 跌破后仍出事件: %s' % (calm_year or '未跌破', events_after_calm or '无'))
    print('  JS 错误:', errors if errors else '无')

    # ---------- 场景C：回归——慢速开荒 80 年仍无民意 ----------
    print()
    print('=== 场景C：回归 · 慢速开荒（1住宅1农庄，80年） ===')
    page.evaluate("""()=>{
      newGame();
      const pi = S.terrain.findIndex(t=>t==='grass');
      S.cells[pi] = {kind:'b', type:'president', lv:1, upg:null};
      S.started = true;
      for (let i=0;i<S.cells.length;i++){
        if (S.cells[i]) continue;
        if (S.terrain[i]==='grass' && !S.cells.some(c=>c&&c.type==='house')){
          S.cells[i] = {kind:'b', type:'house', lv:1, workers:0, limit:0, upg:null, invested:{wood:20}};
        } else if (S.terrain[i]==='grass' && !S.cells.some(c=>c&&c.type==='farm')){
          S.cells[i] = {kind:'b', type:'farm', lv:1, workers:0, limit:6, upg:null, invested:{wood:30}};
        }
      }
    }""")
    run_years(page, 80)
    st = state(page)
    coeff = page.evaluate("()=>moodCoeff('farm')")
    print('  80 年后: 人口 %d | 民意激活 %s | 民意系数 %.2f | 事件 %s' % (
        st['pop'], st['societyOn'], coeff, st['debuff'] or '无'))
    print('  JS 错误:', errors if errors else '无')

    browser.close()
