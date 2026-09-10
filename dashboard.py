# -*- coding: utf-8 -*-
"""HTML 显示页：读取 collector_status.json + 量化库覆盖信息，渲染自包含静态页面。

- render_html(data) 为纯函数：输入状态快照 -> 输出 HTML 文本；
- 页面内嵌 CSS/JS，每 5 秒 fetch 同目录 collector_status.json 自动刷新；
- 无任何外部 CDN/资产依赖，本地 http.server 直接服务。

展示块：状态总览 / 期货行情表 / 期权面板 / OpenVlab波动率地图(下钻) / jiaoyikecha快照 / 告警 / 公告 / 覆盖。
"""
import json
import time

STATUS_FILE_NAME = "collector_status.json"

_CSS = """
:root{--bg:#0e1420;--card:#161d2e;--line:#24304a;--fg:#dbe4f0;--dim:#7d8aa5;
--up:#e05b5b;--down:#37c27a;--accent:#4d9fff;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font:14px/1.6 "Microsoft YaHei",system-ui;padding:16px}
h1{font-size:20px;margin-bottom:4px}
h2{font-size:15px;margin:18px 0 8px;color:var(--accent);border-left:3px solid var(--accent);padding-left:8px}
.sub{color:var(--dim);font-size:12px;margin-bottom:14px}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:6px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.card .k{color:var(--dim);font-size:12px}
.card .v{font-size:18px;font-weight:600;margin-top:2px}
.badge{display:inline-block;border-radius:4px;padding:1px 8px;font-size:12px;margin-left:6px}
.on{background:#123524;color:var(--down)} .off{background:#3a1c1c;color:var(--up)}
table{width:100%;border-collapse:collapse;background:var(--card);border-radius:8px;overflow:hidden}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
th{color:var(--dim);font-weight:400;text-align:right;background:#111827}
td:first-child,th:first-child{text-align:left}
.up{color:var(--up)} .down{color:var(--down)}
.alertline{display:flex;gap:10px;padding:5px 0;border-bottom:1px dashed var(--line);font-size:13px}
.dim{color:var(--dim)} .empty{color:var(--dim);padding:10px;text-align:center}
ul{list-style:none} .news li{padding:4px 0;border-bottom:1px dashed var(--line);font-size:13px}
.m-itm{color:#f0a35e;font-weight:600} .m-otm{color:#6b7a99}
.m-atm{background:rgba(77,159,255,.14);font-weight:600}
.o-spike{background:rgba(224,91,91,.18)} .o-drop{background:rgba(55,194,122,.16)}
.pcr-high{color:#f0a35e;font-weight:600} .pcr-low{color:#37c27a;font-weight:600}
"""

_JS = r"""
async function refresh(){
  try{
    const r = await fetch(STATUS_FILE); if(!r.ok) return;
    const d = await r.json(); render(d);
  }catch(e){ document.getElementById('err').textContent = '状态读取失败: '+e; }
}
// C2（协同）：读取量化项目 reports/latest_report.txt + signals.csv（独立 fetch，失败静默）
async function refreshQuant(){
  try{
    const qs = document.getElementById('quant-html'); if(!qs) return;
    const sig = await fetch(QUANT_SIGNALS); 
    let rows = sig.ok ? await sig.json() : [];
    if(!Array.isArray(rows)) rows = [];
    document.getElementById('quant-signals').textContent = rows.length;
    if(rows.length){
      const last = rows[rows.length-1];
      document.getElementById('quant-sigtime').textContent = last&&last.time?last.time:'--';
    }
    const rep = await fetch(QUANT_REPORT);
    let txt = rep.ok ? await rep.text() : '';
    let cycle = '--';
    if(txt){
      const m = txt.match(/第\s*(\d+)\s*轮/);
      if(m) cycle = '第'+m[1]+'轮';
      document.getElementById('quant-cycle').textContent = cycle;
      // 截取分析总表区段（前 40 行内找【期货分析】到【基本面速览】）
      let seg = txt;
      const i0 = seg.indexOf('【期货分析】');
      const i1 = seg.indexOf('基本面速览');
      if(i0>=0) seg = seg.slice(i0, (i1>i0? i1 : i0+2200));
      qs.innerHTML = '<pre style="font-size:12px;white-space:pre-wrap;word-break:break-all">'+esc(seg)+'</pre>';
    } else {
      qs.innerHTML = '<div class="empty">量化报告未生成（先运行量化 start_monitor.bat）</div>';
    }
  }catch(e){ /* 量化未启动时静默 */ }
}
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function rowHtml(cells, cls){ return '<tr'+(cls||'')+'>'+cells.map(c=>'<td>'+esc(c)+'</td>').join('')+'</tr>'; }
function render(d){
  document.getElementById('sec-updated').textContent = d.updated||'--';
  const sw = d.software||{};
  const mk = (k)=> sw[k]?('<span class="badge on">在线</span>') : '<span class="badge off">离线</span>';
  document.getElementById('sec-legend').innerHTML = (sw.legend?esc(sw.legend.detail||''):'未检测') + (sw.legend?'': '');
  document.getElementById('sec-legend-badge').innerHTML = mk('legend');
  document.getElementById('sec-ths').innerHTML = (sw.ths?esc(sw.ths.detail||''):'未检测');
  document.getElementById('sec-ths-badge').innerHTML = mk('ths');
  document.getElementById('sec-n').textContent = d.collections||0;
  document.getElementById('sec-srcs').textContent = Object.keys(d.sources||{}).length;
  document.getElementById('sec-ocr').textContent = (d.ocr&&d.ocr.available)?'可用':'不可用(截图兜底)';
  // 行情表（点击表头排序）
  const _qSort = window._qSort || {key:'source', dir:1};
  const qCols = ['source','variety','price','chg_pct','bid','ask','volume','open_interest'];
  const qHead = ['源','品种/合约','最新价','涨跌幅','买价','卖价','成交量','持仓量'];
  function renderQuotes(){
    const q = (d.quotes||[]).slice(0,120);
    const k=_qSort.key;
    q.sort((a,b)=>{
      const va = a[k]==null?'':String(a[k]), vb=b[k]==null?'':String(b[k]);
      if(k==='price'||k==='volume'||k==='open_interest'||k==='bid'||k==='ask'){
        return _qSort.dir * ((parseFloat(va)||0) - (parseFloat(vb)||0));
      }
      return _qSort.dir * va.localeCompare(vb);
    });
    const qb = document.getElementById('quotes-body');
    qb.innerHTML = q.length? q.map(x=> rowHtml(qCols.map(c=> x[c]==null?'':x[c]))).join('')
      : '<tr><td colspan="8" class="empty">暂无行情（软件未开或待实测配置）</td></tr>';
    const qh = document.getElementById('quotes-head');
    qh.innerHTML = qCols.map((c,i)=> '<th onclick="window._qSort={key:\''+c+'\',dir:(window._qSort&&window._qSort.key===\''+c+'\'?-window._qSort.dir:1)};renderQuotes()" style="cursor:pointer" title="点击排序">'+qHead[i]+(window._qSort.key===c?(window._qSort.dir>0?' &#9650;':' &#9660;'):'')+'</th>').join('');
  }
  renderQuotes();
  // 期权面板
  const opts = d.options||[];
  document.getElementById('opts-body').innerHTML = opts.length? opts.map(x=> rowHtml([
      x.sym||'', x.expiry||'', x.pcr==null?'':(+x.pcr).toFixed(3), x.atm_iv==null?'':x.atm_iv, x.source||''])).join('')
    : '<tr><td colspan="5" class="empty">暂无期权链数据（实测后接入）</td></tr>';
  // 波动率地图（openvlab，点击下钻曲面）
  const vol = (d.quotes||[]).filter(x=>x.source==='openvlab' && x.iv!=null)
      .sort((a,b)=>(b.iv_percentile||0)-(a.iv_percentile||0)).slice(0,25);
  document.getElementById('vol-body').innerHTML = vol.length? vol.map(x=>
      '<tr onclick="drillDown(&#39;'+esc(x.code||'')+'&#39;)" style="cursor:pointer" title="点击看曲面">'+
      [x.variety||x.code||'', x.code||'', x.iv, x.iv_percentile==null?'':(+x.iv_percentile).toFixed(1)+'%',
      x.iv_1dchg==null?'':x.iv_1dchg, x.skew==null?'':x.skew, x.price==null?'':x.price]
      .map(c=>'<td>'+esc(c)+'</td>').join('')+'</tr>').join('')
    : '<tr><td colspan="7" class="empty">暂无波动率数据（openvlab 源未就绪）</td></tr>';
  // 告警
  const al = d.alerts||[];
  document.getElementById('alerts').innerHTML = al.length? al.map(a=>
      '<div class="alertline"><span class="dim">'+esc(a.ts)+'</span><b>'+esc(a.code)+'</b><span>'+esc(a.reason)+'</span></div>').join('')
    : '<div class="empty">无质量告警</div>';
  // 公告
  const nl = d.news_latest||[];
  document.getElementById('news').innerHTML = nl.length? '<ul class="news">'+nl.map(x=>
      '<li><span class="dim">'+esc(x.ts||'')+'</span> '+esc(x.content||'')+'</li>').join('')+'</ul>'
    : '<div class="empty">暂无公告</div>';
  // 覆盖
  const cv = d.coverage||{}; const cbd=document.getElementById('cov-body');
  cbd.innerHTML = Object.keys(cv).length? Object.entries(cv).map(([k,v])=> rowHtml([
      k, v.bars||0, v.contracts||0, v.first||'', v.last||''])).join('')
    : '<tr><td colspan="5" class="empty">暂无分钟线覆盖（首轮采集后出现）</td></tr>';
  // jiaoyikecha 数据快照
  const jk = d.jykc||{};
  const jcnt=(k)=> jk[k]?jk[k].length:0;
  document.getElementById('jykc-wr').textContent = jcnt('wr');
  document.getElementById('jykc-longhu').textContent = jcnt('longhu');
  document.getElementById('jykc-niuxiong').textContent = jcnt('niuxiong');
  document.getElementById('jykc-hg').textContent = jcnt('hg');
  let jd='';
  if(jk.date){ jd+='<div class="dim" style="padding:4px 0">数据日期: '+esc(jk.date)+'</div>'; }
  const jtab=(title,obj,fmt)=>{ jd+='<h3 style="margin:8px 0 4px;color:var(--accent);font-size:13px">'+title+'</h3>';
    if(!obj||!obj.length){ jd+='<div class="empty">暂无</div>'; return; }
    jd+='<table style="max-width:900px"><tbody>'+obj.slice(0,10).map(x=>'<tr>'+fmt(x).map(c=>'<td>'+esc(c)+'</td>').join('')+'</tr>').join('')+'</tbody></table>'; };
  jtab('仓单日报 Top','wr',x=>[x.variety||x.code||'', '总量 '+ (x.value.total_vol==null?'':(+x.value.total_vol).toLocaleString()), '变化 '+ (x.value.total_chge==null?'':(+x.value.total_chge).toLocaleString())]);
  jtab('龙虎榜 Top','longhu',x=>[x.variety||x.code||'', x.code||'', x.value.longhu==null?'':'龙虎比 '+ (+x.value.longhu).toFixed(2)]);
  jtab('牛熊榜 Top','niuxiong',x=>[x.variety||x.code||'', x.code||'', x.value.niuxiong==null?'':'牛熊 '+ (+x.value.niuxiong).toFixed(0)]);
  jtab('支撑压力位 Top','hg',x=>[x.variety||x.code||'', x.code||'', x.value.current_price==null?'':'现价 '+ (+x.value.current_price).toFixed(0), x.value.min15||'']);
  document.getElementById('jykc-detail').innerHTML = jd;
}
let _drillCode=null, _drillSurf=null;
async function drillDown(code){
  const panel=document.getElementById('drill-panel');
  const body=document.getElementById('drill-body');
  if(_drillCode===code){ panel.style.display='none'; _drillCode=null; return; }
  _drillCode=code; _drillSurf=null; panel.style.display='block';
  body.innerHTML='<div class="empty">加载中…</div>';
  document.getElementById('drill-title').textContent='曲面详情: '+code.toUpperCase();
  try{
    const r=await fetch('openvlab_surfaces/'+code.toLowerCase()+'.json');
    if(!r.ok){body.innerHTML='<div class="empty">暂无该品种曲面快照</div>';return;}
    const d=await r.json(); _drillSurf=d.surface||{};
    const ms=Object.keys(d.surface||{}).sort();
    if(!ms.length){body.innerHTML='<div class="empty">无月份数据</div>';return;}
    let h='<p style="color:var(--dim);margin-bottom:8px">点击月份查看行权价级 T 型链</p><table><thead><tr><th>到期月</th><th>到期日</th><th>剩余天</th><th>ATM 隐波</th><th>前日</th><th>远期价</th><th>看涨OI</th><th>看跌OI</th><th>PCR</th></tr></thead><tbody>';
    for(const e of ms){
      const m=d.surface[e]||{};
      const sc=+m.sum_oi_call||0, sp=+m.sum_oi_put||0;
      const pcr=sc>0?(sp/sc).toFixed(3):'--';
      h+='<tr onclick="drillChain(&#39;'+esc(code)+'&#39;,&#39;'+e+'&#39;)" style="cursor:pointer"><td>'+e+'</td>'
        +'<td>'+(m.expiry_date||'')+'</td><td>'+(m.days_to_expiry==null?'':m.days_to_expiry)+'</td>'
        +'<td>'+(m.atmvol_tday==null?'':m.atmvol_tday)+'</td><td>'+(m.atmvol_yday==null?'':m.atmvol_yday)+'</td>'
        +'<td>'+(m.forward_td==null?'':(+m.forward_td).toFixed(1))+'</td>'
        +'<td>'+(sc||'')+'</td><td>'+(sp||'')+'</td>'
        +'<td class="'+(pcr!=='--'&&parseFloat(pcr)>1.2?'pcr-high':(pcr!=='--'&&parseFloat(pcr)<0.8?'pcr-low':''))+'">'+pcr+'</td></tr>';
    }
    h+='</tbody></table>';
    body.innerHTML=h;
  }catch(e){body.innerHTML='<div class="empty">加载失败: '+e+'</div>';}
}
function _parseMat(v){
  if(v==null) return {};
  if(typeof v==='string'){try{v=JSON.parse(v)}catch(e){return {}}}
  if(Array.isArray(v)){const o={};v.forEach(r=>{if(r&&r.length>=2)o[String(r[0])]=r[1]});return o;}
  return v;
}
function _fv(d,k){const v=d[k]; return v==null?'':v;}
async function drillChain(code,exp){
  if(!_drillSurf||!_drillSurf[exp]) return;
  const ms=_drillSurf[exp];
  const cD=_parseMat(ms.delta_tday_call),pD=_parseMat(ms.delta_tday_put);
  const cI=_parseMat(ms.mktvol_tday_call_bid),pI=_parseMat(ms.mktvol_tday_put_bid);
  const cO=_parseMat(ms.strike_poi_c),pO=_parseMat(ms.strike_poi_p);
  const cOid=_parseMat(ms.strike_oid_c),pOid=_parseMat(ms.strike_oid_p);
  const ts=ms.trading_strike||[];
  const strikes=[...new Set([...Object.keys(cD),...Object.keys(pD),...Object.keys(cO),...Object.keys(pO)])].map(Number).sort((a,b)=>a-b);
  const [lo,hi]=ts.length>=2?[parseFloat(ts[0]),parseFloat(ts[ts.length-1])]:[null,null];
  const f=k=>{const v=k;return lo!=null&&hi!=null?v>=lo-1&&v<=hi+1:true;};
  const rows=strikes.filter(f).map(k=>({strike:k,
    c_iv:_fv(cI,k),c_delta:_fv(cD,k),c_oi:_fv(cO,k),c_oid:_fv(cOid,k),
    p_iv:_fv(pI,k),p_delta:_fv(pD,k),p_oi:_fv(pO,k),p_oid:_fv(pOid,k)}));
  const panel=document.getElementById('chain-panel');
  panel.style.display='block';
  document.getElementById('chain-title').textContent=code.toUpperCase()+' '+exp;
  const fwd=+ms.forward_td||null;
  const atmf=fwd!=null&&rows.length?rows.reduce((a,b)=>Math.abs(a.strike-fwd)<Math.abs(b.strike-fwd)?a:b).strike:null;
  const OI_SPIKE=0.3;
  let h='<table><thead><tr><th>行权价</th><th>看涨隐波</th><th>Call Delta</th><th>Call OI</th><th>Call dOI</th><th>看跌隐波</th><th>Put Delta</th><th>Put OI</th><th>Put dOI</th></tr></thead><tbody>';
  for(const r of rows){
    const cls=[]; if(atmf&&Math.abs(r.strike-atmf)<2) cls.push('m-atm');
    const oC=Math.abs(r.c_oid||0),iC=Math.abs(r.c_oi||0);
    const oP=Math.abs(r.p_oid||0),iP=Math.abs(r.p_oi||0);
    if(iC>0&&oC/iC>OI_SPIKE) cls.push('o-spike');
    if(iP>0&&oP/iP>OI_SPIKE) cls.push('o-spike');
    const dcls=(v,pos)=>{ if(v==null) return ''; const w=pos?v:-v; return w>0.5?'m-itm':'m-otm'; };
    h+='<tr class="'+cls.join(' ')+'"><td>'+r.strike+'</td>'
      +'<td>'+(r.c_iv==null?'':r.c_iv)+'</td>'
      +'<td class="'+dcls(r.c_delta,true)+'">'+(r.c_delta==null?'':r.c_delta)+'</td>'
      +'<td>'+(r.c_oi==null?'':r.c_oi)+'</td><td>'+(r.c_oid==null?'':r.c_oid)+'</td>'
      +'<td>'+(r.p_iv==null?'':r.p_iv)+'</td>'
      +'<td class="'+dcls(r.p_delta,false)+'">'+(r.p_delta==null?'':r.p_delta)+'</td>'
      +'<td>'+(r.p_oi==null?'':r.p_oi)+'</td><td>'+(r.p_oid==null?'':r.p_oid)+'</td></tr>';
  }
  h+='</tbody></table>';
  document.getElementById('chain-body').innerHTML=h;
}
setInterval(refresh, 5000); refresh();
setInterval(refreshQuant, 30000); refreshQuant();
"""

_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>界面操作收集装置</title><style>{css}</style></head>
<body>
<h1>界面操作收集装置 <span class="dim">(本地只读)</span></h1>
<div class="sub" id="err"></div>
<h2>采集状态总览</h2>
<div class="grid">
  <div class="card"><div class="k">Legend <span id="sec-legend-badge"></span></div><div class="v" id="sec-legend">--</div></div>
  <div class="card"><div class="k">同花顺期货通 <span id="sec-ths-badge"></span></div><div class="v" id="sec-ths">--</div></div>
  <div class="card"><div class="k">最近更新</div><div class="v" id="sec-updated">--</div></div>
  <div class="card"><div class="k">采集轮数</div><div class="v" id="sec-n">0</div></div>
  <div class="card"><div class="k">数据源数</div><div class="v" id="sec-srcs">0</div></div>
  <div class="card"><div class="k">OCR</div><div class="v" id="sec-ocr">--</div></div>
</div>
<h2>期货行情表</h2>
<table><thead><tr id="quotes-head"><th>源</th><th>品种</th><th>最新价</th><th>涨跌</th><th>买价</th><th>卖价</th><th>成交量</th><th>持仓量</th></tr></thead><tbody id="quotes-body"></tbody></table>
<h2>期权面板（PCR / 期月 / 隐波）</h2>
<table><thead><tr><th>品种</th><th>到期月</th><th>PCR</th><th>ATM IV</th><th>源</th></tr></thead><tbody id="opts-body"></tbody></table>
<h2>OpenVlab 波动率地图（隐波分位 Top25，点击下钻曲面）</h2>
<table><thead><tr><th>品种</th><th>代码</th><th>平值隐波</th><th>隐波分位</th><th>隐波日变</th><th>偏度</th><th>标的价格</th></tr></thead><tbody id="vol-body"></tbody></table>
<div id="drill-panel" style="display:none"><h2 id="drill-title">曲面详情</h2><div id="drill-body" class="card"></div></div>
<div id="chain-panel" style="display:none"><h2 id="chain-title" style="color:#37c27a">行权价 T 型链</h2><div id="chain-body" class="card" style="max-height:420px;overflow-y:auto"></div></div>
<h2>jiaoyikecha 数据快照（仓单 / 龙虎 / 牛熊 / 支撑压力）</h2>
<div class="grid">
  <div class="card"><div class="k">仓单日报</div><div class="v" id="jykc-wr">--</div></div>
  <div class="card"><div class="k">龙虎榜</div><div class="v" id="jykc-longhu">--</div></div>
  <div class="card"><div class="k">牛熊榜</div><div class="v" id="jykc-niuxiong">--</div></div>
  <div class="card"><div class="k">支撑压力位</div><div class="v" id="jykc-hg">--</div></div>
</div>
<div id="jykc-detail" class="card" style="margin-top:8px"></div>
<h2>量化分析信号（futures_monitor reports）</h2>
<div class="sub" id="quant-sub">读取量化项目 reports/latest_report.txt + signals.csv（每30秒刷新）</div>
<div class="grid">
  <div class="card"><div class="k">最新报告轮次</div><div class="v" id="quant-cycle">--</div></div>
  <div class="card"><div class="k">信号条数</div><div class="v" id="quant-signals">0</div></div>
  <div class="card"><div class="k">最近信号时间</div><div class="v" id="quant-sigtime">--</div></div>
</div>
<div id="quant-html" class="card" style="margin-top:8px;max-height:420px;overflow-y:auto"></div>
<h2>融合质量告警</h2><div id="alerts"></div>
<h2>公告流</h2><div id="news"></div>
<h2>数据覆盖（minute_bars / option_chains）</h2>
<table><thead><tr><th>周期</th><th>bar 数</th><th>合约数</th><th>最早</th><th>最近</th></tr></thead><tbody id="cov-body"></tbody></table>
<script>const STATUS_FILE = '{status_file}';
const QUANT_REPORT = 'quant/latest_report.txt';
const QUANT_SIGNALS = 'quant/signals.csv';{js}</script>
</body></html>
"""


def render_html(data, status_file_name=STATUS_FILE_NAME):
    return _PAGE_TEMPLATE.format(css=_CSS, js=_JS, status_file=status_file_name)


def write_dashboard(data, path=None, status_file_name=STATUS_FILE_NAME):
    import device_config
    path = path or (device_config.data_dir() / "dashboard.html")
    html = render_html(data or {}, status_file_name)
    if hasattr(path, "write_text"):
        path.write_text(html, encoding="utf-8")
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    return str(path)


def collect_dashboard_data(status, include_quant=True):
    data = status.snapshot()
    data["coverage"] = {}
    if include_quant:
        try:
            import fusion
            data["coverage"] = fusion.latest_coverage() or {}
        except Exception:
            pass
    return data