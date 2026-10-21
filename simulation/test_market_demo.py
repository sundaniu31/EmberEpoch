# -*- coding: utf-8 -*-
"""验证市场模拟 Demo：加载、价格波动、事件触发、买卖滑点、收购上限"""
from playwright.sync_api import sync_playwright

from pathlib import Path
_HERE = Path(__file__).resolve().parent
DEMO = (_HERE / 'market_demo.html').as_uri()

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(DEMO)
    pg.wait_for_timeout(500)

    st = lambda: pg.evaluate("""()=>({
      year:S.year, price:S.price, prev:S.prev,
      coin:Math.round(S.player.coin),
      stock:Object.fromEntries(Object.keys(S.player.stock).map(k=>[k,Math.round(S.player.stock[k])])),
      worth:Math.round(netWorth()),
      events:S.events.map(e=>e.nm+'@'+e.cn+'('+e.left+')'),
      orders:S.countries.map(c=>({
        n:c.name, t:c.tname, evt:c.evt,
        buy:Object.fromEntries(Object.entries(c.orders.buy).filter(x=>x[1]>0)),
        sell:Object.fromEntries(Object.entries(c.orders.sell).filter(x=>x[1]>0))
      }))
    })""")

    print('=== 初始状态（已 warm-up 3 年）===')
    s = st()
    print('  第 %d 年 | 价格: 粮%.2f 木%.2f 矿%.2f' % (s['year'], s['price']['grain'], s['price']['wood'], s['price']['ore']))
    print('  玩家: 钱%d 存货%s 净资产%d' % (s['coin'], s['stock'], s['worth']))
    print('  国家:', [(o['n'], o['t']) for o in s['orders']])

    # 跑 30 年，观察波动与事件
    print()
    print('=== 跑 30 年：价格轨迹与事件 ===')
    hist = []
    for i in range(30):
        pg.evaluate("()=>tick(false)")
        s = st()
        hist.append((s['year'], s['price']['grain'], s['price']['wood'], s['price']['ore'], s['events']))
    for y, g, w, o, ev in hist:
        if y % 5 == 0 or ev:
            e = ('  ★事件: ' + ', '.join(ev)) if ev else ''
            print('  第%2d年 粮%.2f 木%.2f 矿%.2f%s' % (y, g, w, o, e))
    gs = [h[1] for h in hist]; ws = [h[2] for h in hist]; os_ = [h[3] for h in hist]
    print('  30年区间: 粮 %.2f~%.2f | 木 %.2f~%.2f | 矿 %.2f~%.2f' % (
        min(gs), max(gs), min(ws), max(ws), min(os_), max(os_)))
    allEv = set()
    for h in hist:
        for e in h[4]:
            allEv.add(e.split('@')[0])
    print('  触发过的事件类型:', allEv or '无')

    # 买卖测试
    print()
    print('=== 交易测试：收购上限与滑点 ===')
    pg.evaluate("()=>{ S.player.coin = 5000; S.player.stock.ore = 400; }")
    before = st()
    print('  卖前: 矿价%.2f 玩家矿%d 钱%d' % (before['price']['ore'], before['stock']['ore'], before['coin']))
    # 小额卖出（应被各国买单吸收）
    pg.evaluate("""()=>{ document.getElementById('tGood').value='ore';
                         document.getElementById('tQty').value=20; doSell(); }""")
    a = st()
    print('  卖 20: 矿价%.2f 得钱%d （均价 %.2f/单位）' % (
        a['price']['ore'], a['coin']-before['coin'], (a['coin']-before['coin'])/20))
    # 大额卖出（超出收购上限 → 砸价）
    before2 = st()
    pg.evaluate("""()=>{ document.getElementById('tGood').value='ore';
                          document.getElementById('tQty').value=300; doSell(); }""")
    bch = st()
    got = bch['coin']-before2['coin']
    print('  卖 300: 矿价%.2f→%.2f 得钱%d （均价 %.2f/单位）' % (
        before2['price']['ore'], bch['price']['ore'], got, got/300))
    print('  滑点验证: 小额均价 %.3f > 大额均价 %.3f → %s' % (
        (a['coin']-before['coin'])/20, got/300,
        '✓ 通过' if (a['coin']-before['coin'])/20 > got/300 else '✗ 失败'))

    # 买入抬价（先注入金币再取基准，避免把注入额算进花费）
    pg.evaluate("()=>{ S.player.coin = 20000; }")
    b3 = st()
    pg.evaluate("""()=>{ document.getElementById('tGood').value='ore';
                         document.getElementById('tQty').value=400; doBuy(); }""")
    b4 = st()
    print('  买 400: 矿价%.2f→%.2f 花钱%d（均价 %.2f/单位）' % (
        b3['price']['ore'], b4['price']['ore'], b3['coin']-b4['coin'], (b3['coin']-b4['coin'])/400))
    print('  抬价验证:', '✓ 通过' if b4['price']['ore'] > b3['price']['ore'] else '✗ 失败')

    # 价格粘性：单年变动不超过 25%
    print()
    print('=== 价格粘性验证（单年 |涨跌| ≤ 25%）===')
    pg.evaluate("()=>{ init(); }")
    viol = 0
    for i in range(60):
        pvp = pg.evaluate("()=>Object.assign({},S.price)")
        pg.evaluate("()=>tick(false)")
        pn = pg.evaluate("()=>S.price")
        for g in ['grain','wood','ore']:
            if abs(pn[g]-pvp[g])/pvp[g] > 0.26: viol += 1
    print('  60 年 × 3 商品 = 180 次年度变动，超限(>26%)次数:', viol, '→', '✓ 通过' if viol==0 else '✗ 失败')

    print()
    print('JS 错误:', errs if errs else '无')
    b.close()
