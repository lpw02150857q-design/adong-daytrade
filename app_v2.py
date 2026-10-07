import os, math, requests
from flask import Flask, jsonify, Response

app=Flask(__name__)
KEY=os.environ.get("FUGLE_API_KEY","")
BASE="https://api.fugle.tw/marketdata/v1.0/stock"

PAGE=r"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>阿東台股當沖雷達</title>
<style>body{margin:0;background:#07111e;color:#eef5ff;font-family:system-ui}.w{max-width:1000px;margin:auto;padding:14px}.card{background:#111f32;border:1px solid #263b55;border-radius:16px;padding:14px;margin:10px 0}button{padding:12px 16px;border:0;border-radius:10px;background:#67a8ff;font-weight:800}table{width:100%;border-collapse:collapse}th,td{padding:10px 5px;border-bottom:1px solid #263b55;text-align:right}th:first-child,td:first-child{text-align:left}.g{color:#42dc99}.y{color:#ffd166}.r{color:#ff7474}.m{color:#9eb1c9;font-size:13px}@media(max-width:650px){body{font-size:14px}th:nth-child(5),td:nth-child(5){display:none}}</style></head>
<body><div class=w><h2>阿東台股當沖雷達</h2><div class=card><button onclick=scan()>立即掃描</button> <span id=s class=m>等待開始</span><div class=m>每日額度50萬｜排除國巨2327｜掃描上市/上櫃活躍股｜只保留可現股當沖</div></div>
<div class=card><table><thead><tr><th>股票</th><th>現價</th><th>分數</th><th>漲跌</th><th>成交量</th><th>訊號</th><th>張數</th></tr></thead><tbody id=r><tr><td colspan=7>按「立即掃描」</td></tr></tbody></table></div><div class=card id=d><b>分析</b><div class=m>點股票查看風控參考。</div></div></div>
<script>let data={};const f=n=>Number(n||0).toLocaleString('zh-TW',{maximumFractionDigits:2});async function scan(){s.textContent='掃描中…';try{let x=await fetch('/api/scan').then(x=>x.json());if(x.error)throw Error(x.error);data={};x.stocks.forEach(v=>data[v.symbol]=v);r.innerHTML=x.stocks.length?x.stocks.map(v=>{let z=v.score>=80?['🟢強勢觀察','g']:v.score>=65?['🟡等待確認','y']:['⚪不進場','r'];return `<tr onclick="detail('${v.symbol}')"><td><b>${v.symbol} ${v.name}</b></td><td>${f(v.price)}</td><td>${v.score}</td><td class=${v.change>=0?'g':'r'}>${v.change.toFixed(2)}%</td><td>${f(v.volume)}</td><td class=${z[1]}>${z[0]}</td><td>${v.lots}</td></tr>`}).join(''):'<tr><td colspan=7>目前無符合條件股票</td></tr>';s.textContent='更新 '+new Date().toLocaleTimeString()}catch(e){s.textContent='錯誤：'+e.message}}function detail(k){let v=data[k];d.innerHTML=`<b>${v.symbol} ${v.name}</b><br>現價 ${f(v.price)}｜評分 ${v.score}/100｜日內振幅 ${v.range.toFixed(2)}%<br>50萬上限最多約 ${v.lots} 張｜防守參考 ${f(v.stop)}｜第一目標 ${f(v.tp1)}｜第二目標 ${f(v.tp2)}<div class=m>機械風控參考，不代表保證成交或獲利。</div>`}setInterval(scan,60000);</script></body></html>"""

def get(path):
    r=requests.get(BASE+path,headers={"X-API-KEY":KEY},timeout=12); r.raise_for_status(); return r.json()

@app.get("/")
def home(): return Response(PAGE,mimetype="text/html")

@app.get("/api/scan")
def scan():
    if not KEY: return jsonify({"error":"Render 尚未設定 FUGLE_API_KEY"}),500
    symbols=[]
    for market in ("TSE","OTC"):
        try:
            d=get(f"/snapshot/actives/{market}?trade=volume")
            a=d.get("data",d) if isinstance(d,dict) else d
            if isinstance(a,list): symbols += [str(x["symbol"]) for x in a[:25] if x.get("symbol")]
        except Exception as e: return jsonify({"error":f"活躍股 API 失敗：{e}"}),500
    symbols=list(dict.fromkeys(x for x in symbols if x!="2327"))[:35]
    out=[]
    for sym in symbols:
        try:
            t=get(f"/intraday/ticker/{sym}")
            if t.get("canDayTrade") is False: continue
            q=get(f"/intraday/quote/{sym}")
            p=float(q.get("lastPrice") or q.get("closePrice") or 0)
            prev=float(q.get("previousClose") or q.get("referencePrice") or 0)
            hi=float(q.get("highPrice") or p); lo=float(q.get("lowPrice") or p)
            total=q.get("total") or {}; vol=float(total.get("tradeVolume") or q.get("tradeVolume") or 0)
            ch=(p-prev)/prev*100 if prev else 0; rng=(hi-lo)/lo*100 if lo else 0
            score=max(0,min(100,round(50+max(-15,min(20,ch*4))+min(15,rng*3)+min(15,math.log10(max(1,vol))*2))))
            risk=max(.01,p-lo)
            out.append({"symbol":sym,"name":t.get("name",""),"price":p,"change":ch,"range":rng,"volume":vol,"score":score,
                        "lots":int(500000//(p*1000)) if p else 0,"stop":lo,"tp1":p+risk*1.5,"tp2":p+risk*2.2})
        except Exception as e: continue
    out.sort(key=lambda x:x["score"],reverse=True)
    return jsonify({"stocks":out[:10]})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
