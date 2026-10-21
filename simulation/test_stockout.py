# -*- coding: utf-8 -*-
"""验证"没货"会发生什么：库存负数、买不到、无交易时的价格行为"""
from playwright.sync_api import sync_playwright

from pathlib import Path
_HERE = Path(__file__).resolve().parent
DEMO = (_HERE / 'market_demo.html').as_uri()

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(DEMO); pg.wait_for_timeout(400)

    # ---------- 1. 长跑：库存会不会变负？买不到多少次？ ----------
    print('=== 1. 长跑 60 年：库存负值 / 买不到 ===')
    pg.evaluate("()=>init()")
    minStock = 999; negYears = 0; shortfalls = 0
    for i in range(60):
        pg.evaluate("()=>tick(false)")
        d = pg.evaluate("""()=>({
          min: Math.min(...S.countries.flatMap(c=>Object.values(c.stock))),
          neg: S.countries.some(c=>Object.values(c.stock).some(v=>v<0)),
          coin: S.countries.map(c=>Math.round(c.coin))
        })""")
        minStock = min(minStock, d['min'])
        if d['neg']: negYears += 1
    logs = pg.evaluate("()=>S.log.filter(l=>l.t.includes('只买到')).length")
    print('  各国库存历史最小值: %d' % minStock)
    print('  出现负库存的年数: %d / 60' % negYears)
    print('  "想买只买到X" 记录条数: %d' % logs)
    coins = pg.evaluate("()=>S.countries.map(c=>Math.round(c.coin))")
    print('  60年后各国金币:', coins)

    # ---------- 2. 极端：市场完全无货（各国库存清零、不生产） ----------
    print()
    print('=== 2. 极端场景：所有国家停产且库存归零 ===')
    pg.evaluate("""()=>{
      init();
      S.countries.forEach(c=>{
        c.produce = {};                                  // 全部停产
        Object.keys(c.stock).forEach(g=>c.stock[g]=0);   // 库存清零
        c.need = {grain:60, wood:40, ore:40};            // 但仍在需求
      });
    }""")
    traj = []
    for i in range(12):
        pg.evaluate("()=>tick(true)")
        traj.append(pg.evaluate("()=>({g:S.price.grain,w:S.price.wood,o:S.price.ore})"))
    print('  粮价轨迹:', ' → '.join('%.2f' % t['g'] for t in traj))
    print('  矿价轨迹:', ' → '.join('%.2f' % t['o'] for t in traj))
    print('  说明: 供给=0 时 ratio=D/1 被 clamp 到 2.60 → 价格顶格（受 ±25% 限速逐年爬升）')

    # ---------- 3. 反向：市场完全无交易（无买也无卖） ----------
    print()
    print('=== 3. 反向场景：无人买也无人卖（D=0, S=0）===')
    pg.evaluate("""()=>{
      init();
      S.countries.forEach(c=>{ c.produce={}; c.need={};
        Object.keys(c.stock).forEach(g=>c.stock[g]=100); });
    }""")
    traj2 = []
    for i in range(12):
        pg.evaluate("()=>tick(true)")
        traj2.append(pg.evaluate("()=>({g:S.price.grain,w:S.price.wood,o:S.price.ore})"))
    print('  粮价轨迹:', ' → '.join('%.2f' % t['g'] for t in traj2))
    print('  矿价轨迹:', ' → '.join('%.2f' % t['o'] for t in traj2))
    print('  ↑ 若价格无故暴跌，说明 D=0 时 ratio=0 被 clamp 到下限，是逻辑缺陷')

    # ---------- 4. 玩家没粮时 ----------
    print()
    print('=== 4. 玩家口粮耗尽 ===')
    pg.evaluate("""()=>{ init(); S.player.stock.grain = 0; S.player.coin = 5000;
                         S.player.produce = {}; }""")   # 停产才能真正触发缺粮
    c0 = pg.evaluate("()=>Math.round(S.player.coin)")
    pg.evaluate("()=>tick(false)")
    d = pg.evaluate("""()=>({coin:Math.round(S.player.coin), grain:Math.round(S.player.stock.grain),
                             log:S.log[0].t})""")
    print('  花钱 %d（高价购粮 2.2 倍价），剩余粮 %d' % (c0-d['coin'], d['grain']))
    print('  日志:', d['log'])

    # ---------- 5. 玩家钱不够且没粮（会不会负资产） ----------
    print()
    print('=== 5. 玩家没粮且没钱 ===')
    pg.evaluate("""()=>{ init(); S.player.stock.grain = 0; S.player.coin = 0;
                         S.player.produce = {}; }""")
    pg.evaluate("()=>tick(false)")
    d = pg.evaluate("()=>({coin:Math.round(S.player.coin), worth:Math.round(netWorth())})")
    print('  金币: %d（负数即为欠债，当前无破产判定）| 净资产: %d' % (d['coin'], d['worth']))

    print()
    print('JS 错误:', errs if errs else '无')
    b.close()
