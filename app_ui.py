# -*- coding: utf-8 -*-
"""
yeppi - UI / Flask routes layer
===============================
This file contains the Flask app, API routes, and embedded HTML/CSS/JS UI.
The fuzzy recommendation logic is imported from fuzzy_logic_core.py.

Run:
    pip install -r requirements.txt
    python app_ui.py
Then open http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os

from flask import Flask, jsonify, render_template_string, request

import fuzzy_logic_core as core

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


# ============================================================
# 1) FLASK ROUTES / API ENDPOINTS
# ============================================================
@app.get("/")
def index():
    try:
        meta = core.meta_payload()
        error = ""
    except Exception as exc:
        meta = {"categories": [], "cuisines": [], "tastes": [], "health_goals": [], "rain_levels": []}
        error = str(exc)
    return render_template_string(UI_TEMPLATE, meta_json=json.dumps(meta, ensure_ascii=False), boot_error=error)


@app.get("/api/meta")
def api_meta():
    try:
        return jsonify({"ok": True, **core.meta_payload()})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/search_suggestions")
def api_search_suggestions():
    try:
        q = request.args.get("q", "")
        return jsonify({"ok": True, "suggestions": core.build_search_suggestions(q, 8)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "suggestions": []}), 500


@app.post("/api/recommend")
def api_recommend():
    try:
        return jsonify(core.recommend(request.get_json(force=True) or {}))
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.get("/api/restaurant/<rid>")
def api_restaurant(rid: str):
    rest = core.get_restaurant_by_id(rid)
    if not rest:
        return jsonify({"ok": False, "error": "Không tìm thấy quán"}), 404
    return jsonify({"ok": True, "restaurant": core.serialize_result(rest)})


@app.get("/api/route/<rid>")
def api_route(rid: str):
    rest = core.get_restaurant_by_id(rid)
    if not rest:
        return jsonify({"ok": False, "error": "Không tìm thấy quán"}), 404
    user_lat = float(request.args.get("user_lat", core.DEFAULT_USER_LAT))
    user_lng = float(request.args.get("user_lng", core.DEFAULT_USER_LNG))
    route = core.get_route_geometry(rest, user_lat, user_lng)
    return jsonify({"ok": True, "route": route})


@app.post("/api/create_order")
def api_create_order():
    ok, payload, status = core.create_order(request.get_json(force=True) or {})
    return jsonify({"ok": ok, **payload}), status


@app.get("/api/tracking/<order_id>")
def api_tracking(order_id: str):
    ok, payload, status = core.get_order_status(order_id)
    return jsonify({"ok": ok, **payload}), status


# ============================================================
# 2) UI TEMPLATE - HTML/CSS/JS EMBEDDED IN PYTHON UI FILE
# ============================================================
UI_TEMPLATE = r'''
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>yeppi - đặt món quanh UEH</title>
  <link rel="icon" type="image/png" href="/static/yeppi-logo-icon.png" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800;900&family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin=""/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
  <style>
    :root{--bg:#fff4e6;--card:#fffaf4;--line:#eadfd2;--dark:#17191f;--muted:#7c746d;--orange:#ff6b3a;--orange2:#ff9a3d;--teal:#28c7b8;--green:#20b26b;--blue:#3b82f6;--shadow:0 28px 70px rgba(50,30,10,.16);}
    *{box-sizing:border-box} body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;background:radial-gradient(circle at 8% 10%,#ffe7cd 0,transparent 28%),radial-gradient(circle at 82% 90%,#dffdf7 0,transparent 26%),linear-gradient(135deg,#fff2df,#fffaf2);color:var(--dark);min-height:100vh;overflow-x:hidden}.app-bg:before,.app-bg:after{content:"";position:fixed;border-radius:999px;filter:blur(16px);z-index:-1}.app-bg:before{width:520px;height:520px;background:rgba(250,111,58,.12);left:-150px;top:-180px}.app-bg:after{width:620px;height:620px;background:rgba(40,199,184,.13);right:-250px;bottom:-260px}.layout{min-height:100vh;display:grid;grid-template-columns:minmax(280px,440px) minmax(430px,520px) minmax(280px,440px);align-items:center;gap:32px;padding:32px 54px}.brand{align-self:start;padding-top:6px}.brand h1{font-size:42px;letter-spacing:-1.4px;margin:0 0 8px;font-weight:900}.pill-dark{display:inline-flex;align-items:center;gap:8px;border-radius:999px;background:var(--dark);color:#fff;padding:9px 14px;font-size:12px;font-weight:800}.brand p{font-size:14px;line-height:1.8;color:var(--muted);max-width:430px}.brand .orange{color:var(--orange);font-weight:900}.side-card{align-self:start;background:rgba(255,255,255,.72);backdrop-filter:blur(18px);border:1px solid rgba(40,20,0,.1);border-radius:26px;padding:20px;box-shadow:0 18px 45px rgba(40,20,0,.08)}.side-card h3{margin:0 0 10px;font-size:16px}.side-card p,.side-card li{font-size:12px;line-height:1.65;color:#6d645d}.side-card b{color:var(--orange)}.phone-frame{width:430px;height:900px;background:#0d0e13;border-radius:62px;padding:10px;box-shadow:0 40px 90px rgba(15,15,20,.35);position:relative;margin:auto}.phone-frame:before{content:"";position:absolute;top:18px;left:50%;transform:translateX(-50%);width:116px;height:30px;background:#08090d;border-radius:999px;z-index:50}.phone{position:relative;width:100%;height:100%;overflow:hidden;border-radius:52px;background:#fff4e6}.status{height:34px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;font-size:12px;font-weight:900}.screen{display:none;height:calc(100% - 34px);overflow-y:auto;padding:4px 18px 98px}.screen.active{display:block}.screen::-webkit-scrollbar,.h-scroll::-webkit-scrollbar{display:none}.h-scroll{overflow-x:auto;display:flex;gap:9px;scrollbar-width:none}.topbar{display:flex;align-items:center;justify-content:space-between;margin-top:6px}.location{font-size:12px;color:var(--muted);font-weight:700}.headline{font-size:25px;line-height:1.08;margin:4px 0 0;font-weight:900;letter-spacing:-.8px}.round-btn{border:0;border-radius:999px;background:#fff;box-shadow:0 8px 22px rgba(40,20,0,.08);height:44px;width:44px;display:grid;place-items:center;font-size:18px;cursor:pointer}.loc-mini{margin-left:6px;border:0;border-radius:999px;background:#fff4ec;color:var(--wine,#9b4049);font-weight:900;cursor:pointer;padding:2px 7px;box-shadow:0 6px 14px rgba(95,43,38,.10)}.search-row{display:flex;gap:10px;margin:16px 0 12px}.search{flex:1;border:1px solid var(--line);background:#fff;border-radius:19px;display:flex;align-items:center;gap:8px;padding:0 14px}.search input{border:0;outline:0;background:transparent;height:48px;width:100%;font-weight:700}.filter-btn{border:0;background:var(--dark);color:#fff;border-radius:18px;width:50px;font-size:19px}.smart-card{background:linear-gradient(135deg,var(--orange),#ff7c3e 58%,var(--orange2));border-radius:28px;padding:16px;color:#fff;box-shadow:0 18px 45px rgba(255,107,58,.28);position:relative;overflow:hidden}.smart-card:after{content:"";position:absolute;right:-35px;top:-42px;width:160px;height:160px;border-radius:999px;background:rgba(255,255,255,.16)}.smart-card h2{font-size:20px;line-height:1.1;margin:9px 0 8px;font-weight:900}.smart-card p{font-size:12px;line-height:1.55;margin:0;color:rgba(255,255,255,.86)}.mini-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}.mini-chip{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.17);border-radius:15px;padding:8px 6px;text-align:center;font-size:11px;font-weight:800}.cta-white{width:100%;border:0;border-radius:17px;background:#fff;color:var(--orange);padding:13px;margin-top:12px;font-weight:900}.section-title{display:flex;align-items:end;justify-content:space-between;margin:18px 0 10px}.section-title h2{margin:0;font-size:18px;letter-spacing:-.4px}.section-title p{margin:4px 0 0;font-size:11px;color:var(--muted)}.cat-chip{border:1px solid var(--line);background:#fff;border-radius:17px;padding:10px 12px;font-size:12px;font-weight:850;color:#3e3934;white-space:nowrap;cursor:pointer}.cat-chip.active{background:var(--dark);color:#fff;border-color:var(--dark);box-shadow:0 12px 24px rgba(15,17,23,.16)}.info-box{background:#fff;border:1px solid var(--line);border-radius:22px;padding:13px;display:flex;gap:11px;align-items:flex-start;margin:11px 0}.info-icon{min-width:36px;height:36px;border-radius:14px;background:#fff0e8;display:grid;place-items:center}.info-box h4{margin:0;font-size:13px}.info-box p{margin:3px 0 0;font-size:11px;line-height:1.55;color:var(--muted)}.rest-list{display:flex;flex-direction:column;gap:12px}.rest-card{background:#fff;border:1px solid rgba(40,20,0,.08);border-radius:28px;padding:11px;box-shadow:0 10px 28px rgba(40,20,0,.07);cursor:pointer;transition:.18s transform}.rest-card:active{transform:scale(.985)}.rest-main{display:flex;gap:12px}.food-img{width:104px;height:104px;object-fit:cover;border-radius:23px;background:#ffe7cf}.rest-title-row{display:flex;justify-content:space-between;gap:7px}.rest-name{font-size:15px;font-weight:900;margin:2px 0 2px;line-height:1.18}.rest-sub{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:205px}.meta-row{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}.tag{display:inline-flex;align-items:center;gap:3px;background:#f5eee6;border-radius:999px;padding:5px 8px;font-size:10px;font-weight:850;color:#675d55}.score-badge{background:#fff0e8;color:var(--orange);border-radius:999px;padding:5px 8px;font-size:10px;font-weight:900}.reason{margin-top:9px;background:#fff4ec;border:1px solid #ffe1cf;border-radius:16px;padding:9px;font-size:11px;color:#6a5e55;line-height:1.45}.price-row{display:flex;align-items:center;justify-content:space-between;margin-top:7px}.price{font-size:12px;font-weight:900}.add-btn{border:0;background:var(--orange);color:#fff;border-radius:999px;width:32px;height:32px;font-weight:900}.bottom-nav{position:absolute;left:18px;right:18px;bottom:16px;z-index:42;background:#15171d;border-radius:28px;padding:8px;display:flex;justify-content:space-around;box-shadow:0 22px 40px rgba(0,0,0,.22)}.nav-btn{position:relative;border:0;background:transparent;color:rgba(255,255,255,.55);border-radius:19px;flex:1;padding:8px 4px;font-size:10px;font-weight:850;cursor:pointer}.nav-btn span{display:block;font-size:18px;margin-bottom:2px}.nav-btn.active{background:#fff;color:#15171d}.cart-count{position:absolute;top:3px;right:18px;min-width:17px;height:17px;border-radius:999px;background:var(--orange);color:#fff;font-size:10px;display:grid;place-items:center}.sheet,.detail{position:absolute;inset:0;z-index:70;background:rgba(15,16,20,.45);display:none;align-items:flex-end}.sheet.open,.detail.open{display:flex}.sheet-panel{width:100%;max-height:84%;overflow:auto;background:#fff4e6;border-radius:36px 36px 0 0;padding:20px 18px 28px;box-shadow:0 -20px 60px rgba(0,0,0,.16)}.sheet-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}.sheet-head h2{margin:0;font-size:21px;font-weight:900}.close{border:0;background:#fff;border-radius:999px;width:38px;height:38px;font-size:18px}.field-card{background:#fff;border:1px solid var(--line);border-radius:24px;padding:14px;margin-bottom:12px}.field-title{display:flex;justify-content:space-between;align-items:center;font-size:13px;font-weight:900;margin-bottom:10px}.range{width:100%;accent-color:var(--orange)}.split{display:grid;grid-template-columns:1fr 1fr;gap:10px}.choice-row{display:flex;gap:8px;flex-wrap:wrap}.choice{border:1px solid var(--line);background:#fff;border-radius:999px;padding:9px 12px;font-size:12px;font-weight:850;cursor:pointer}.choice.active{background:var(--dark);color:#fff;border-color:var(--dark)}.choice.taste.active{background:var(--orange);border-color:var(--orange)}.primary-btn,.ghost-btn{border:0;border-radius:18px;padding:14px 16px;font-weight:900;cursor:pointer}.primary-btn{background:var(--orange);color:#fff;box-shadow:0 16px 30px rgba(255,107,58,.22)}.ghost-btn{background:#fff;color:#222;border:1px solid var(--line)}.detail{background:#fff4e6;display:none;align-items:stretch;overflow:auto}.detail.open{display:block}.hero{height:265px;position:relative;background:#ffe2cb}.hero img{width:100%;height:100%;object-fit:cover}.hero:after{content:"";position:absolute;inset:0;background:linear-gradient(to bottom,rgba(0,0,0,.08),rgba(0,0,0,.12))}.back{position:absolute;top:18px;left:18px;z-index:2;border:0;border-radius:999px;width:42px;height:42px;background:rgba(255,255,255,.92);font-size:18px}.detail-body{position:relative;margin-top:-34px;background:#fff4e6;border-radius:34px 34px 0 0;padding:18px 18px 110px}.detail-card{background:#fff;border:1px solid var(--line);border-radius:28px;padding:16px;box-shadow:0 12px 30px rgba(40,20,0,.08)}.detail-card h2{margin:0;font-size:24px;line-height:1.1}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:14px 0}.metric{background:#f8f0e8;border-radius:18px;padding:10px;text-align:center}.metric b{font-size:12px}.metric small{display:block;font-size:10px;color:var(--muted);margin-top:3px}.route-map,.main-map,.track-map{height:245px;border-radius:28px;overflow:hidden;border:1px solid var(--line);background:#e7f4ef}.main-map{height:380px}.track-map{height:285px}.menu-item{background:#fff;border:1px solid var(--line);border-radius:23px;padding:10px;display:flex;gap:10px;align-items:center;margin-bottom:10px}.menu-item img{width:62px;height:62px;object-fit:cover;border-radius:17px}.menu-info{flex:1}.menu-info h4{margin:0 0 4px;font-size:13px}.empty{background:#fff;border:1px solid var(--line);border-radius:28px;text-align:center;padding:30px 18px;color:var(--muted)}.cart-line{background:#fff;border:1px solid var(--line);border-radius:22px;padding:12px;display:flex;align-items:center;justify-content:space-between;margin-bottom:9px}.qty{display:flex;align-items:center;gap:8px}.qty button{border:0;border-radius:999px;width:28px;height:28px;background:#f0e8df;font-weight:900}.summary-card{background:#fff;border:1px solid var(--line);border-radius:28px;padding:16px;margin-top:13px}.summary-line{display:flex;justify-content:space-between;margin:8px 0;font-size:13px}.tracking-card{background:#15171d;color:#fff;border-radius:28px;padding:16px;margin-top:14px}.timeline{display:flex;flex-direction:column;gap:12px;margin-top:12px}.step{display:flex;align-items:center;gap:10px;color:rgba(255,255,255,.55);font-size:13px;font-weight:800}.dot{width:30px;height:30px;border-radius:999px;background:rgba(255,255,255,.14);display:grid;place-items:center}.step.active{color:#fff}.step.active .dot{background:var(--orange)}.profile-head{background:#15171d;color:#fff;border-radius:32px;padding:18px;display:flex;gap:14px;align-items:center}.avatar{width:64px;height:64px;border-radius:999px;background:var(--orange);display:grid;place-items:center;font-size:30px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}.tile{background:#fff;border:1px solid var(--line);border-radius:24px;padding:14px}.tile p{font-size:11px;color:var(--muted);margin:9px 0 3px}.tile b{font-size:14px}.loader{padding:22px;text-align:center;color:var(--muted);font-weight:800}.pulse{animation:pulse 1.4s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.45}}.map-pin{background:#fff;border:3px solid var(--orange);width:34px;height:34px;border-radius:50%;display:grid;place-items:center;box-shadow:0 8px 20px rgba(0,0,0,.16)}.user-pin{background:#15171d;color:#fff;border:3px solid #fff}.rider-pin{background:var(--teal);color:#fff;border-color:#fff}.toast{position:absolute;left:24px;right:24px;bottom:96px;z-index:120;background:#15171d;color:#fff;border-radius:18px;padding:13px 16px;font-size:12px;font-weight:850;display:none}.toast.show{display:block}.alert{border-radius:20px;border:1px solid #ffd1b9;background:#fff3ec;color:#8b3d1d;padding:12px;font-size:12px;line-height:1.5;margin:10px 0;font-weight:700}.search-wrap{position:relative;flex:1}.search-clear{border:0;background:#f8e8dd;color:var(--wine,#9b4049);border-radius:999px;width:26px;height:26px;font-weight:900;cursor:pointer;display:none}.search-panel{display:none;position:absolute;left:0;right:0;top:58px;z-index:65;background:#fffaf5;border:1px solid rgba(151,59,68,.16);border-radius:20px;box-shadow:0 18px 38px rgba(95,43,38,.16);overflow:hidden}.search-panel.open{display:block}.search-suggestion{width:100%;border:0;background:transparent;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;color:#4b2d27;font-weight:800;cursor:pointer;text-align:left}.search-suggestion:hover{background:#fff0e7}.search-suggestion small{font-size:10px;color:#9b7a70;font-weight:800}.search-chip-row{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;margin:-2px 0 12px}.search-chip-row::-webkit-scrollbar{display:none}.search-chip{flex:0 0 auto;border:1px solid rgba(151,59,68,.16);background:#fffaf5;color:#7d3038;border-radius:999px;padding:7px 11px;font-size:11px;font-weight:900;cursor:pointer}.search-chip.active{background:#7d3038;color:#fff}.boot-error{background:#fff;border:1px solid #ffb4a4;color:#a12b17;border-radius:22px;padding:16px;margin:18px;font-size:13px;line-height:1.6}.leaflet-control-attribution{font-size:9px!important}@media (max-width:1050px){.layout{grid-template-columns:1fr;padding:20px}.brand,.side-card{display:none}.phone-frame{width:min(430px,100vw - 18px);height:calc(100vh - 18px);border-radius:42px;padding:0;box-shadow:none;background:transparent}.phone{border-radius:36px}.phone-frame:before{display:none}.status{padding-top:4px}.screen{padding-left:16px;padding-right:16px}}
    body{font-family:"Be Vietnam Pro","Segoe UI",Tahoma,Arial,sans-serif;text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased}
    button,input,select,textarea{font:inherit;letter-spacing:0}
    .brand-logo{display:flex;align-items:center;gap:12px;margin-bottom:8px}
    .brand-logo h1{margin:0;font-size:46px;letter-spacing:0}
    .logo-mark,.mini-mark{display:inline-grid;place-items:center;background:linear-gradient(135deg,#ff6b3a,#28c7b8);color:#fff;font-weight:900;box-shadow:0 12px 28px rgba(255,107,58,.22)}
    .logo-mark{width:52px;height:52px;border-radius:18px;font-size:30px}
    .mini-mark{width:24px;height:24px;border-radius:9px;font-size:15px}
    .app-mini{display:flex;align-items:center;gap:7px;margin-bottom:8px;color:var(--dark);font-size:14px;font-weight:900;letter-spacing:0}
    .headline,.section-title h2,.brand h1{letter-spacing:0;line-height:1.18}
    .location{font-size:13px;line-height:1.45;white-space:normal}
    .quick-cats{position:relative;margin:4px -18px 0;padding:0 18px 4px;overflow-x:auto;display:flex;gap:8px;scroll-snap-type:x proximity;scrollbar-width:none}
    .quick-cats::-webkit-scrollbar{display:none}
    .quick-cats:after{content:"";position:sticky;right:-18px;min-width:24px;background:linear-gradient(90deg,rgba(255,244,230,0),#fff4e6 78%)}
    .cat-chip{display:inline-flex;align-items:center;justify-content:center;gap:7px;flex:0 0 auto;min-width:92px;min-height:38px;max-width:148px;border-radius:999px;white-space:nowrap;line-height:1.1;text-align:center;padding:9px 13px;scroll-snap-align:start;box-shadow:0 8px 18px rgba(40,20,0,.05);overflow:hidden;text-overflow:ellipsis}
    .cat-chip .cat-icon{font-size:15px;line-height:1}
    .cat-chip .cat-label{overflow:hidden;text-overflow:ellipsis}
    .cat-chip.active{transform:translateY(-1px);box-shadow:0 14px 26px rgba(15,17,23,.18)}
    .cat-chip.all{min-width:82px}
    .info-box{line-height:1.45}
    .reason b{font-weight:900}
    @media (max-width:390px){.headline{font-size:23px}.quick-cats{margin-left:-14px;margin-right:-14px;padding-left:14px;padding-right:14px}.cat-chip{font-size:11px;min-width:86px;padding:8px 11px}.screen{padding-left:14px;padding-right:14px}}

    /* Poster-inspired Yeppi visual refresh */
    :root{
      --bg:#fff3e9;--card:#fffaf4;--line:#ead2c3;--dark:#3b1f1b;--muted:#8a6c62;
      --orange:#9b4049;--orange2:#c1666b;--teal:#6f8f56;--green:#6f8f56;--blue:#9b4049;
      --wine:#8f3842;--wine-dark:#5a2925;--cream:#fff6ee;--cream2:#f8e7d8;
      --shadow:0 22px 58px rgba(95,43,38,.16);
    }
    body{
      background:linear-gradient(135deg,#fff7ee 0%,#fce8dc 52%,#fff8f0 100%);
      color:var(--dark);
    }
    .app-bg:before,.app-bg:after{display:none}
    .layout{gap:42px}
    .brand-logo{align-items:center;gap:18px}
    .logo-mark{
      width:72px;height:72px;border-radius:20px;background:linear-gradient(145deg,#c56a73,#87323c);
      box-shadow:0 18px 38px rgba(143,56,66,.25);font-size:0;position:relative;overflow:hidden;
    }
    .logo-mark:before{content:"🍜";font-size:34px;line-height:1}
    .brand-logo h1{
      text-transform:uppercase;font-size:64px;letter-spacing:0;color:var(--wine);
      text-shadow:0 8px 20px rgba(143,56,66,.10);
    }
    .brand .pill-dark{background:transparent;color:var(--dark);padding:0;font-size:16px;font-weight:600}
    .brand p{font-size:16px;color:#4f342e;line-height:1.65}
    .brand .orange{color:var(--wine);font-weight:800}
    .side-card{
      background:rgba(255,250,244,.78);border-color:rgba(151,59,68,.16);border-radius:30px;
      box-shadow:0 22px 55px rgba(95,43,38,.12);
    }
    .side-card h3{color:var(--wine);font-size:18px}
    .phone-frame{
      background:linear-gradient(145deg,#191312,#050505);box-shadow:0 42px 100px rgba(43,18,15,.34);
    }
    .phone{background:linear-gradient(180deg,#fff6ee 0%,#fff1e5 62%,#fff9f3 100%)}
    .status{color:#231413;padding-inline:28px}
    .screen{padding-top:10px}
    .topbar{align-items:flex-start;margin-top:8px}
    .app-mini{margin-bottom:8px;color:var(--wine);font-size:16px;text-transform:uppercase;letter-spacing:0}
    .mini-mark{
      width:34px;height:34px;border-radius:12px;background:linear-gradient(145deg,#bf626b,#87323c);
      box-shadow:0 12px 24px rgba(143,56,66,.20);font-size:0;position:relative;
    }
    .mini-mark:before{content:"🍜";font-size:17px}
    .location{color:#6e5148;font-weight:700}
    .headline{font-size:30px;color:#2f1713;font-weight:900;letter-spacing:0}
    .round-btn,.filter-btn,.close,.back{
      background:#fffaf5;color:var(--wine);border:1px solid rgba(151,59,68,.16);
      box-shadow:0 12px 26px rgba(95,43,38,.10);
    }
    .filter-btn{width:50px;border-radius:17px;font-size:18px}
    .search{
      height:52px;border:0;background:rgba(255,255,255,.88);border-radius:18px;
      box-shadow:0 13px 28px rgba(95,43,38,.10);color:var(--wine);
    }
    .search input{height:52px;color:#5a332d}
    .search input::placeholder{color:#b79085;font-weight:600}
    .smart-card{
      min-height:170px;padding:18px 128px 18px 18px;background:linear-gradient(135deg,#743127 0%,#963f3d 58%,#c57b5f 100%);
      border:1px solid rgba(255,255,255,.24);border-radius:20px;box-shadow:0 22px 40px rgba(117,49,39,.24);
    }
    .smart-card:before{
      content:"";position:absolute;right:-18px;bottom:-24px;width:156px;height:156px;border-radius:50%;
      background:url("https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=360&q=80") center/cover;
      border:9px solid rgba(255,243,232,.95);box-shadow:0 18px 34px rgba(52,22,17,.28);z-index:1;
    }
    .smart-card:after{
      right:42px;top:14px;width:56px;height:56px;background:rgba(255,230,192,.18);
      border:1px solid rgba(255,255,255,.12);
    }
    .smart-card>*{position:relative;z-index:2}
    .smart-card .pill-dark{
      background:rgba(255,247,238,.18)!important;border:1px solid rgba(255,255,255,.20);
      padding:7px 11px;font-size:11px;
    }
    .smart-card h2{font-size:20px;max-width:178px}
    .smart-card p{max-width:190px;color:rgba(255,255,255,.92)}
    .mini-grid{grid-template-columns:1fr;max-width:112px;gap:6px;margin-top:10px}
    .mini-chip{
      border-radius:999px;background:rgba(255,255,255,.16);border-color:rgba(255,255,255,.18);
      padding:6px 9px;font-size:10px;text-align:left;
    }
    .cta-white{
      width:auto;min-width:118px;border-radius:999px;padding:10px 14px;margin-top:10px;
      background:#fff7ee;color:var(--wine);box-shadow:0 10px 22px rgba(45,17,14,.20);
    }
    .section-title{margin:22px 0 12px}
    .section-title h2{font-size:17px;color:#311914}
    .section-title p{color:#8c7066}
    .quick-cats{gap:14px;margin:2px -18px 0;padding-bottom:8px}
    .quick-cats:after{background:linear-gradient(90deg,rgba(255,246,238,0),#fff6ee 78%)}
    .cat-chip{
      width:70px;min-width:70px;max-width:70px;min-height:84px;padding:0;gap:7px;flex-direction:column;
      background:transparent;border:0;box-shadow:none;color:#4c302b;overflow:visible;
    }
    .cat-chip .cat-icon{
      width:54px;height:54px;border-radius:19px;background:#fffaf5;display:grid;place-items:center;
      font-size:24px;box-shadow:0 12px 24px rgba(95,43,38,.12);border:1px solid rgba(151,59,68,.12);
    }
    .cat-chip .cat-label{
      width:76px;font-size:10px;line-height:1.18;color:#5a3b34;white-space:normal;text-align:center;
      display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
    }
    .cat-chip.active{background:transparent;border:0;color:var(--wine);transform:none;box-shadow:none}
    .cat-chip.active .cat-icon{background:var(--wine);color:#fff;border-color:var(--wine)}
    .cat-chip.active .cat-label{color:var(--wine);font-weight:900}
    .info-box,.summary-card,.field-card,.tile,.empty{
      background:rgba(255,250,245,.92);border-color:rgba(151,59,68,.14);
      border-radius:22px;box-shadow:0 12px 26px rgba(95,43,38,.08);
    }
    .info-icon{background:#f8ded5;color:var(--wine)}
    .rest-card{
      border-radius:18px;background:rgba(255,250,245,.94);border-color:rgba(151,59,68,.14);
      box-shadow:0 16px 32px rgba(95,43,38,.10);
    }
    .food-img{width:92px;height:92px;border-radius:16px}
    .rest-name{color:#3a1d19}
    .tag{background:#f8e8dd;color:#6b443c}
    .score-badge{background:#f4dad2;color:var(--wine)}
    .reason{background:#fff0e7;border-color:#edc9ba;color:#6a463d}
    .price,.reason b{color:var(--wine)!important}
    .add-btn,.primary-btn{
      background:linear-gradient(145deg,#a3464f,#7d3038);box-shadow:0 12px 24px rgba(143,56,66,.22);
    }
    .ghost-btn,.choice{background:#fffaf5;border-color:rgba(151,59,68,.18);color:#4b2d27}
    .choice.active,.choice.taste.active{background:var(--wine);border-color:var(--wine);color:#fff}
    .bottom-nav{
      left:14px;right:14px;bottom:14px;background:rgba(255,250,245,.96);border:1px solid rgba(151,59,68,.16);
      border-radius:24px;padding:7px;box-shadow:0 22px 44px rgba(95,43,38,.18);
    }
    .nav-btn{color:#9b7a70;border-radius:18px;font-size:9px}
    .nav-btn span{font-size:17px}
    .nav-btn.active{background:#fff1e8;color:var(--wine)}
    .cart-count{background:var(--wine)}
    .sheet-panel,.detail,.detail-body{background:#fff3e9}
    .sheet-head h2,.detail-card h2{color:#321a15}
    .hero{background:#f6d7c8}
    .detail-card,.menu-item,.cart-line{
      background:#fffaf5;border-color:rgba(151,59,68,.14);border-radius:20px;
    }
    .tracking-card,.profile-head{
      background:linear-gradient(135deg,#703029,#963f46);box-shadow:0 18px 36px rgba(95,43,38,.18);
    }
    .avatar{background:#fff1e8;color:var(--wine)}
    .route-map,.main-map,.track-map{border-color:rgba(151,59,68,.18);border-radius:22px}
    .map-pin{border-color:var(--wine)}
    .user-pin{background:var(--wine)}
    .toast{background:#5a2925;border-radius:18px}
    .alert{background:#fff0e7;border-color:#e8c0b4;color:#7d3038}

    /* Cleaner desktop intro panels */
    .brand .pill-dark{
      display:inline-flex;align-items:center;gap:8px;margin:4px 0 14px;
      color:var(--wine);font-size:17px;font-weight:800;letter-spacing:-.2px;
    }
    .brand p{max-width:460px;margin:14px 0;font-size:17px;line-height:1.78;color:#4f342e}
    .brand p.orange{font-size:17px;color:var(--wine);font-weight:900;line-height:1.65}
    .side-card{max-width:480px;padding:28px 30px}
    .side-card p,
    .side-card li{font-size:13px;line-height:1.76;color:#6d5149}
    .side-card h3{color:var(--wine);font-size:20px;margin:0 0 12px;font-weight:900;letter-spacing:-.2px}
    .side-card h3:not(:first-child){margin-top:18px}
    .side-card ol{padding-left:20px;margin:10px 0 16px}
    .side-card li{margin-bottom:8px}
    @media (max-width:1050px){
      .phone{border-radius:36px}
      .screen{padding-left:18px;padding-right:18px}
      .quick-cats{margin-left:-18px;margin-right:-18px}
    }
    @media (max-width:390px){
      .headline{font-size:27px}.smart-card{padding-right:112px}.smart-card:before{width:136px;height:136px}
      .cat-chip{width:66px;min-width:66px}.cat-chip .cat-icon{width:50px;height:50px}
    }
  
    /* ============================================================
       UI PATCH: prettier search suggestions + in-phone detail view
       ============================================================ */
    .search-wrap{position:relative;flex:1;min-width:0}
    .search-panel{
      display:none;
      position:absolute;
      left:0;right:0;top:58px;
      z-index:88;
      background:rgba(255,250,245,.96);
      border:1px solid rgba(151,59,68,.16);
      border-radius:24px;
      box-shadow:0 20px 46px rgba(95,43,38,.18);
      padding:8px;
      max-height:286px;
      overflow-y:auto;
      overflow-x:hidden;
      backdrop-filter:blur(16px);
      scrollbar-width:none;
    }
    .search-panel::-webkit-scrollbar{display:none}
    .search-panel.open{display:block;animation:searchDrop .16s ease-out}
    @keyframes searchDrop{from{opacity:0;transform:translateY(-6px) scale(.98)}to{opacity:1;transform:translateY(0) scale(1)}}
    .search-suggestion{
      width:100%;
      border:0;
      background:transparent;
      display:grid;
      grid-template-columns:34px minmax(0,1fr) auto;
      align-items:center;
      gap:10px;
      padding:10px;
      color:#4b2d27;
      cursor:pointer;
      text-align:left;
      border-radius:18px;
      transition:.16s ease;
    }
    .search-suggestion:hover{background:#fff0e7;transform:translateX(2px)}
    .search-suggestion:active{transform:scale(.985)}
    .sug-icon{
      width:34px;height:34px;border-radius:14px;
      display:grid;place-items:center;
      background:linear-gradient(135deg,#fff2e8,#f7dfd8);
      color:#943642;
      box-shadow:inset 0 0 0 1px rgba(151,59,68,.08);
      font-size:15px;
      flex:0 0 auto;
    }
    .sug-main{min-width:0;display:flex;flex-direction:column;gap:2px}
    .sug-title{
      display:block;
      font-size:12.5px;
      line-height:1.25;
      font-weight:900;
      color:#3b1e19;
      white-space:nowrap;
      overflow:hidden;
      text-overflow:ellipsis;
      max-width:100%;
    }
    .sug-sub{
      display:block;
      font-size:10px;
      font-weight:750;
      color:#a07e73;
      white-space:nowrap;
      overflow:hidden;
      text-overflow:ellipsis;
    }
    .sug-type{
      justify-self:end;
      max-width:82px;
      padding:6px 8px;
      border-radius:999px;
      background:#f3e1d9;
      color:#8f5f57;
      font-size:9.5px;
      font-weight:900;
      line-height:1;
      white-space:nowrap;
      overflow:hidden;
      text-overflow:ellipsis;
    }
    .search-suggestion.loading .sug-icon{animation:pulse 1.1s infinite}
    .detail{
      position:absolute!important;
      inset:34px 0 0 0!important;
      z-index:76!important;
      display:none;
      background:#fff3e9!important;
      border-radius:0 0 52px 52px!important;
      overflow:hidden!important;
      align-items:stretch!important;
      box-shadow:inset 0 1px 0 rgba(255,255,255,.55);
    }
    .detail.open{display:block!important}
    .detail-scroller{
      height:100%;
      overflow-y:auto;
      overflow-x:hidden;
      background:linear-gradient(180deg,#fff0e5 0%,#fff7ef 45%,#fff2e8 100%);
      scrollbar-width:none;
    }
    .detail-scroller::-webkit-scrollbar{display:none}
    .detail .hero{
      height:226px;
      border-radius:0;
      overflow:hidden;
      background:#f4dccd;
    }
    .detail .hero img{transform:scale(1.01)}
    .detail .hero:after{
      background:linear-gradient(to bottom,rgba(39,18,13,.04),rgba(39,18,13,.26));
    }
    .detail .back{
      top:14px;left:14px;
      width:44px;height:44px;
      background:rgba(255,255,255,.94);
      color:#8f3440;
      box-shadow:0 12px 28px rgba(52,25,18,.18);
      font-weight:900;
    }
    .detail-body{
      margin-top:-30px;
      border-radius:34px 34px 0 0;
      padding:18px 18px 116px;
      background:linear-gradient(180deg,#fff7ef 0%,#fff2e8 100%);
    }
    .detail-card{
      border-radius:28px;
      background:rgba(255,250,246,.96);
      border:1px solid rgba(151,59,68,.13);
      box-shadow:0 16px 42px rgba(68,35,24,.10);
    }
    .detail-card h2{
      font-size:22px;
      line-height:1.16;
      letter-spacing:-.5px;
      color:#301610;
    }
    .detail .rest-sub{font-size:11px;color:#8a665d}
    .metrics{gap:9px}
    .metric{
      border-radius:20px;
      background:#f5ece5;
      box-shadow:inset 0 0 0 1px rgba(151,59,68,.04);
    }
    .metric b{font-size:12.5px;color:#321a15}
    .detail .tag{background:#f2dfd5;color:#78453f}
    .detail .reason{
      background:#fff2ec;
      border-color:#f3c8b7;
      border-radius:20px;
      font-size:11.5px;
    }
    .detail .section-title{margin:18px 0 10px}
    .detail .section-title h2{font-size:17px}
    .route-map{
      height:220px;
      border-radius:24px;
      box-shadow:0 12px 30px rgba(72,42,28,.08);
    }
    .detail .menu-item{
      border-radius:22px;
      background:rgba(255,250,246,.96);
      box-shadow:0 10px 26px rgba(68,35,24,.06);
    }
    .detail .menu-item img{width:60px;height:60px;border-radius:17px}
    @media (max-width:1050px){
      .phone-frame{
        width:min(430px,calc(100vw - 20px))!important;
        height:min(900px,calc(100vh - 20px))!important;
        padding:10px!important;
        border-radius:52px!important;
        background:#0d0e13!important;
        box-shadow:0 28px 70px rgba(15,15,20,.28)!important;
      }
      .phone-frame:before{display:block!important;top:18px!important}
      .phone{border-radius:42px!important}
      .detail{border-radius:0 0 42px 42px!important}
      .screen{padding-left:16px;padding-right:16px}
    }

  
    /* =======================================================
       Detail screen safe-frame fix
       Keep restaurant detail inside the same iPhone frame as
       Home/Map/Cart screens. The detail view scrolls internally
       and does not visually cover the phone bottom frame.
       ======================================================= */
    .phone{isolation:isolate}
    .detail{
      position:absolute!important;
      inset:34px 0 0 0!important;
      width:100%!important;
      height:auto!important;
      z-index:76!important;
      display:none;
      background:linear-gradient(180deg,#fff7ef 0%,#fff0e6 62%,#fff9f4 100%)!important;
      border-radius:0 0 42px 42px!important;
      overflow:hidden!important;
      align-items:stretch!important;
      box-shadow:inset 0 1px 0 rgba(255,255,255,.6);
    }
    .detail.open{display:block!important}
    .detail-scroller{
      height:100%!important;
      max-height:100%!important;
      overflow-y:auto!important;
      overflow-x:hidden!important;
      padding:8px 18px 142px!important;
      background:transparent!important;
      scrollbar-width:none;
      overscroll-behavior:contain;
      -webkit-overflow-scrolling:touch;
    }
    .detail-scroller::-webkit-scrollbar{display:none!important}
    .detail .hero{
      height:216px!important;
      margin:4px 0 0!important;
      border-radius:30px!important;
      overflow:hidden!important;
      background:#f4dccd!important;
      box-shadow:0 18px 38px rgba(61,32,23,.12)!important;
    }
    .detail .hero img{
      width:100%!important;
      height:100%!important;
      object-fit:cover!important;
      transform:scale(1.01);
    }
    .detail .hero:after{
      border-radius:30px!important;
      background:linear-gradient(to bottom,rgba(37,17,11,.04),rgba(37,17,11,.22))!important;
    }
    .detail .back{
      top:26px!important;
      left:32px!important;
      width:44px!important;
      height:44px!important;
      background:rgba(255,255,255,.95)!important;
      color:#8f3440!important;
      box-shadow:0 12px 28px rgba(52,25,18,.18)!important;
      font-weight:900!important;
    }
    .detail-body{
      margin-top:-28px!important;
      padding:0!important;
      background:transparent!important;
      border-radius:0!important;
      position:relative;
      z-index:2;
    }
    .detail-card{
      border-radius:30px!important;
      padding:16px!important;
      margin:0!important;
      background:rgba(255,250,246,.97)!important;
      border:1px solid rgba(151,59,68,.13)!important;
      box-shadow:0 16px 42px rgba(68,35,24,.10)!important;
    }
    .detail-card h2{
      font-size:22px!important;
      line-height:1.16!important;
      letter-spacing:-.55px!important;
      color:#301610!important;
    }
    .detail .rest-sub{font-size:11px!important;color:#8a665d!important}
    .detail .metrics{gap:9px!important;margin:14px 0!important}
    .detail .metric{
      border-radius:20px!important;
      background:#f5ece5!important;
      box-shadow:inset 0 0 0 1px rgba(151,59,68,.04)!important;
      padding:10px 6px!important;
    }
    .detail .metric b{font-size:12.5px!important;color:#321a15!important}
    .detail .metric small{font-size:10px!important}
    .detail .tag{
      background:#f2dfd5!important;
      color:#78453f!important;
      max-width:100%;
    }
    .detail .reason{
      background:#fff2ec!important;
      border-color:#f3c8b7!important;
      border-radius:20px!important;
      font-size:11.5px!important;
    }
    .detail .section-title{margin:18px 4px 10px!important}
    .detail .section-title h2{font-size:17px!important}
    .detail .route-map{
      height:218px!important;
      border-radius:24px!important;
      box-shadow:0 12px 30px rgba(72,42,28,.08)!important;
    }
    .detail .menu-item{
      border-radius:22px!important;
      background:rgba(255,250,246,.97)!important;
      box-shadow:0 10px 26px rgba(68,35,24,.06)!important;
    }
    .detail .menu-item img{width:60px!important;height:60px!important;border-radius:17px!important}
    @media (max-width:1050px){
      .phone-frame{
        width:min(430px,calc(100vw - 20px))!important;
        height:min(900px,calc(100vh - 20px))!important;
        padding:10px!important;
        border-radius:52px!important;
        background:#0d0e13!important;
        box-shadow:0 28px 70px rgba(15,15,20,.28)!important;
      }
      .phone-frame:before{display:block!important;top:18px!important}
      .phone{border-radius:42px!important}
      .detail{border-radius:0 0 42px 42px!important}
      .detail-scroller{padding-left:18px!important;padding-right:18px!important;padding-bottom:142px!important}
    }



    /* FINAL FRAME FIX: overlays now live inside .phone, so they must be clipped
       to the white screen instead of the black device frame. */
    .phone > .sheet,
    .phone > .detail{
      position:absolute!important;
      width:auto!important;
      max-width:100%!important;
      overflow:hidden!important;
    }
    .phone > .sheet{
      inset:0!important;
      z-index:74!important;
      border-radius:0 0 52px 52px!important;
      background:rgba(38,20,17,.42)!important;
      align-items:flex-end!important;
    }
    .phone > .sheet.open{display:flex!important}
    .phone > .sheet .sheet-panel{
      max-height:calc(100% - 34px)!important;
      overscroll-behavior:contain;
      -webkit-overflow-scrolling:touch;
    }
    .phone > .detail{
      inset:34px 0 0 0!important;
      z-index:86!important;
      border-radius:0 0 52px 52px!important;
      background:linear-gradient(180deg,#fff7ef 0%,#fff0e6 62%,#fff9f4 100%)!important;
    }
    .phone > .detail.open{display:block!important}
    .phone > .detail .detail-scroller{
      height:100%!important;
      min-height:0!important;
      overflow-y:auto!important;
      overflow-x:hidden!important;
      overscroll-behavior:contain;
      -webkit-overflow-scrolling:touch;
    }
    .phone > .detail .route-map,
    .phone > .detail .leaflet-container{
      max-width:100%!important;
    }
    @media (max-width:1050px){
      .phone > .sheet{border-radius:0 0 42px 42px!important}
      .phone > .detail{border-radius:0 0 42px 42px!important}
    }
    .logo-mark,.mini-mark{
      display:block!important;
      object-fit:cover;
      background:transparent!important;
      color:transparent!important;
      padding:0;
    }
    .logo-mark{
      width:72px!important;
      height:72px!important;
      border-radius:20px!important;
      box-shadow:0 18px 38px rgba(143,56,66,.25)!important;
    }
    .mini-mark{
      width:34px!important;
      height:34px!important;
      border-radius:12px!important;
      box-shadow:0 12px 24px rgba(143,56,66,.20)!important;
      flex:0 0 auto;
    }
    .quick-cats{
      width:100%!important;
      max-width:100%!important;
      margin:2px 0 0!important;
      padding:0 2px 8px!important;
      gap:8px!important;
      align-items:flex-start!important;
      overflow-x:auto!important;
      overflow-y:hidden!important;
    }
    .quick-cats:after{display:none!important}
    .cat-chip{
      width:64px!important;
      min-width:64px!important;
      max-width:64px!important;
      min-height:78px!important;
      padding:0!important;
      gap:6px!important;
    }
    .cat-chip .cat-icon{
      width:50px!important;
      height:50px!important;
      border-radius:18px!important;
      font-size:22px!important;
    }
    .cat-chip .cat-label{
      width:64px!important;
      font-size:10px!important;
      line-height:1.16!important;
      overflow:hidden!important;
      text-align:center!important;
      word-break:normal;
    }
    @media (max-width:390px){
      .quick-cats{gap:7px!important;padding-inline:0!important}
      .cat-chip{width:60px!important;min-width:60px!important;max-width:60px!important}
      .cat-chip .cat-icon{width:48px!important;height:48px!important}
      .cat-chip .cat-label{width:60px!important;font-size:9.5px!important}
    }
  </style>
</head>
<body class="app-bg">
  <div class="layout">
    <aside class="brand">
      <div class="brand-logo">
        <img class="logo-mark" src="/static/yeppi-logo-icon.png" alt="Yeppi logo" />
        <h1>YEPPI</h1>
      </div>

      <span class="pill-dark">AI food suggestion · delivery around you</span>

      <p>
        Yeppi là app gợi ý món ăn cho những lúc bạn không biết nên ăn gì.
        Chỉ cần nhập ngân sách, mức đói, thời gian muốn nhận món và khẩu vị,
        Yeppi sẽ tự tìm ra những quán phù hợp nhất.
      </p>

      <p>
        App không chỉ lọc món theo danh mục, mà còn tính thêm khoảng cách,
        thời gian giao, giờ mở cửa, mức giá, sức khỏe và độ hợp khẩu vị để
        đưa ra gợi ý hợp lý hơn.
      </p>

      <p class="orange">
        Ăn gì hôm nay? Để Yeppi chọn giúp bạn nhanh hơn, đúng ý hơn.
      </p>
    </aside>

    <main class="phone-frame">
      <div class="phone">
        <div class="status"><span id="statusClock">--:--</span><span>◔ 5G ▰</span></div>
        {% if boot_error %}<div class="boot-error">{{ boot_error }}</div>{% endif %}

        <section id="home" class="screen active">
          <div class="topbar">
            <div><div class="app-mini"><img class="mini-mark" src="/static/yeppi-logo-icon.png" alt="" /><b>Yeppi</b></div><div class="location">📍 Giao đến <span id="userLabel">UEH cơ sở B, Quận 10</span> <button class="loc-mini" onclick="getCurrentLocation()" title="Dùng vị trí hiện tại">⌖</button></div><div class="headline">Không biết ăn gì?</div></div>
            <button class="round-btn" onclick="openSheet('needsSheet')">👤</button>
          </div>
          <div class="search-row"><div class="search-wrap"><div class="search">🔎 <input id="searchInput" placeholder="Tìm món, quán, cuisine..." autocomplete="off" /><button id="searchClear" class="search-clear" onclick="clearSearchInput()" title="Xóa tìm kiếm">×</button></div><div id="searchPanel" class="search-panel"></div></div><button class="filter-btn" onclick="openSheet('filterSheet')">☰</button></div>
          <div id="searchChips" class="search-chip-row"></div>
          <div class="smart-card">
            <span class="pill-dark" style="background:rgba(255,255,255,.22);color:#fff">✨ Yeppi gợi ý</span>
            <h2 id="smartTitle">Để Yeppi lo!</h2>
            <p id="smartText">Gợi ý món phù hợp với khẩu vị, ngân sách và thời gian của bạn.</p>
            <div class="mini-grid"><div class="mini-chip" id="budgetMini">180.000đ</div><div class="mini-chip" id="peopleMini">2 người</div><div class="mini-chip" id="timeMini">45 phút</div></div>
            <button class="cta-white" onclick="openSheet('needsSheet')">Tùy chỉnh nhu cầu →</button>
          </div>
          <div class="section-title"><div><h2>Danh mục phổ biến</h2><p>Chọn món đang thèm hoặc để Yeppi tự chọn</p></div></div>
          <div id="categoryBar" class="quick-cats" aria-label="Phân loại nhanh"></div>
          <div id="modeBox" class="info-box"></div>
          <div class="section-title"><div><h2>Gợi ý dành cho bạn</h2><p id="resultSub">Đang cân bằng giá, vị trí và ETA</p></div><button class="choice" onclick="switchTab('map')">Xem map</button></div>
          <div id="warningBox"></div>
          <div id="resultList" class="rest-list"><div class="loader pulse">Đang tải gợi ý...</div></div>
          <div id="explainBox" class="info-box"></div>
        </section>

        <section id="map" class="screen">
          <div class="topbar"><div><div class="location">🗺️ Giao đến <span id="mapUserLabel">UEH cơ sở B, Quận 10</span></div><div class="headline">Quán gần bạn</div></div><button class="round-btn" onclick="refreshRecommendations()">↻</button></div>
          <div id="mainMap" class="main-map" style="margin-top:14px"></div>
          <div class="section-title"><div><h2>Gần nhất & phù hợp nhất</h2><p>Chạm vào quán để xem route</p></div></div>
          <div id="mapList" class="rest-list"></div>
        </section>

        <section id="orders" class="screen">
          <div class="topbar"><div><div class="location">🛒 Checkout</div><div class="headline">Giỏ hàng</div></div><button class="round-btn" onclick="switchTab('home')">＋</button></div>
          <div id="cartBox"></div>
          <div id="trackingBox"></div>
        </section>

        <section id="profile" class="screen">
          <div class="profile-head"><div class="avatar">y</div><div><h2 style="margin:0">Bạn trên yeppi</h2><p style="margin:5px 0 0;color:rgba(255,255,255,.62);font-size:12px">Sở thích đặt món hôm nay</p></div></div>
          <div class="grid2">
            <div class="tile"><span>💸</span><p>Budget/người</p><b id="profileBudget">90.000đ</b></div>
            <div class="tile"><span>🥗</span><p>Sức khỏe</p><b id="profileHealth">Normal</b></div>
            <div class="tile"><span>⏱️</span><p>Thời gian</p><b id="profileTime">45 phút</b></div>
            <div class="tile"><span>🌧️</span><p>Thời tiết</p><b id="profileRain">Không mưa</b></div>
          </div>
          <div class="summary-card"><h3 style="margin:0 0 10px">Khẩu vị ưu tiên</h3><div id="profileTastes" class="choice-row"></div></div>
        </section>

        <nav class="bottom-nav">
          <button class="nav-btn active" data-tab="home" onclick="switchTab('home')"><span>🏠</span>Home</button>
          <button class="nav-btn" data-tab="map" onclick="switchTab('map')"><span>🧭</span>Map</button>
          <button class="nav-btn" data-tab="orders" onclick="switchTab('orders')"><span>🧾</span>Đơn <em id="cartCount" class="cart-count" style="display:none">0</em></button>
          <button class="nav-btn" data-tab="profile" onclick="switchTab('profile')"><span>👤</span>Tôi</button>
        </nav>
        <div id="toast" class="toast"></div>

        <div id="needsSheet" class="sheet"><div class="sheet-panel"><div class="sheet-head"><h2>Nhu cầu hôm nay</h2><button class="close" onclick="closeSheet('needsSheet')">×</button></div>
        <div class="field-card"><div class="field-title"><span>📍 Địa chỉ giao hàng</span><b id="locationStatus">Mặc định</b></div><div id="locationText" style="font-size:12px;color:var(--muted);line-height:1.5;margin-bottom:10px">UEH cơ sở B, 279 Nguyễn Tri Phương, Quận 10</div><div class="split"><button class="ghost-btn" onclick="getCurrentLocation()">Dùng vị trí hiện tại</button><button class="ghost-btn" onclick="resetDefaultLocation()">Về UEH</button></div><p style="font-size:10px;color:var(--muted);line-height:1.45;margin:9px 0 0">Yeppi dùng tọa độ này để tính lại khoảng cách đường đi, ETA và thứ tự gợi ý. Để tránh sai địa chỉ, app không tự bịa tên phường/quận từ GPS.</p></div>
        <div class="field-card"><div class="field-title"><span>💸 Ngân sách tổng</span><b id="budgetVal"></b></div><input id="budgetRange" class="range" type="range" min="10000" max="1000000" step="10000" /></div>
        <div class="split"><div class="field-card"><div class="field-title"><span>👥 Số người</span><b id="peopleVal"></b></div><input id="peopleRange" class="range" type="range" min="1" max="10" step="1" /></div><div class="field-card"><div class="field-title"><span>⏰ Giờ đặt</span><b id="clockMode">Thực tế</b></div><input id="timeOfDay" type="time" style="width:100%;border:0;background:#f8f0e8;border-radius:15px;padding:12px;font-weight:900" /><button class="ghost-btn" style="width:100%;margin-top:8px;padding:10px" onclick="useCurrentTimeNow()">Dùng giờ hiện tại</button></div></div>
        <div class="field-card"><div class="field-title"><span>🔥 Mức đói</span><b id="hungerVal"></b></div><input id="hungerRange" class="range" type="range" min="1" max="10" step="1" /></div>
        <div class="field-card"><div class="field-title"><span>⏱️ Muốn nhận trong</span><b id="deliveryVal"></b></div><input id="deliveryRange" class="range" type="range" min="10" max="120" step="5" /></div>
        <div class="field-card"><div class="field-title"><span>🥗 Mục tiêu sức khỏe</span></div><div id="healthChoices" class="choice-row"></div></div>
        <div id="dietPrefCard" class="field-card" style="display:none"><div class="field-title"><span>🥬 Kiểu Diet</span><b id="dietPrefVal">Mặn</b></div><div id="dietPreferenceChoices" class="choice-row"></div><p style="font-size:10px;color:var(--muted);line-height:1.45;margin:9px 0 0">Ăn chay là ràng buộc cứng: Yeppi chỉ giữ quán chay và không fallback sang quán mặn.</p></div>
        <div class="field-card"><div class="field-title"><span>🌧️ Thời tiết</span></div><div id="rainChoices" class="choice-row"></div></div>
        <button class="primary-btn" style="width:100%" onclick="applyNeeds()">Xem gợi ý phù hợp</button>
      </div></div>

      <div id="filterSheet" class="sheet"><div class="sheet-panel"><div class="sheet-head"><h2>Phân loại & bộ lọc</h2><button class="close" onclick="closeSheet('filterSheet')">×</button></div>
        <div class="field-card"><div class="field-title"><span>🍽️ Bạn đang thèm gì?</span></div><div id="categoryChoices" class="choice-row"></div></div>
        <div class="field-card"><div class="field-title"><span>🌏 Cuisine</span></div><div id="cuisineChoices" class="choice-row"></div></div>
        <div class="field-card"><div class="field-title"><span>😋 Khẩu vị</span></div><div id="tasteChoices" class="choice-row"></div></div>
        <div class="split"><button class="ghost-btn" onclick="clearFilters()">Xóa lọc</button><button class="primary-btn" onclick="applyFilters()">Áp dụng</button></div>
      </div></div>

        <div id="detailModal" class="detail"></div>
      </div>
    </main>

    <aside class="side-card">
      <h3>Yeppi hoạt động như thế nào?</h3>

      <p>
        Yeppi dùng logic mờ để hiểu các nhu cầu không rõ ràng của người dùng,
        ví dụ như “hơi đói”, “muốn giao nhanh”, “ngân sách vừa phải” hoặc
        “muốn ăn lành mạnh hơn”.
      </p>

      <p>
        <b>Khi bạn chưa chọn món:</b> Yeppi tự suy luận nhóm món phù hợp.
        <br>
        <b>Khi bạn đã chọn danh mục:</b> app giữ đúng nhóm món đó và chỉ nới
        các điều kiện như khoảng cách, ngân sách hoặc cuisine nếu cần.
      </p>

      <h3>Trải nghiệm chính</h3>
      <ol>
        <li>Nhập nhu cầu: ngân sách, số người, mức đói, thời gian nhận món.</li>
        <li>Chọn một hoặc nhiều danh mục món nếu đã có ý định.</li>
        <li>Yeppi gợi ý quán theo điểm phù hợp, ETA và khoảng cách thực tế.</li>
        <li>Xem menu, thêm món vào giỏ và đặt hàng.</li>
        <li>Theo dõi đơn hàng trên bản đồ theo thời gian thực.</li>
      </ol>

      <p>
        <b>Điểm mạnh:</b> gợi ý có giải thích, lọc đúng ý định người dùng,
        và phù hợp hơn với bối cảnh thật của mỗi bữa ăn.
      </p>
    </aside>
  </div>

<script>
const META = {{ meta_json | safe }};
const bootError = {{ boot_error | tojson }};
function currentBrowserHHMM(){const d=new Date();return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')}
function updateStatusClock(){const el=document.getElementById('statusClock'); if(el) el.textContent=currentBrowserHHMM();}
const DEFAULT_LOCATION = {
  lat: META.default_user?.lat || 10.76126399256893,
  lng: META.default_user?.lng || 106.66836872382974,
  label: META.default_user?.label || 'UEH cơ sở B, 279 Nguyễn Tri Phương, Quận 10'
};
let useRealTime = true;
const state = {
  total_budget: 180000, group_size: 2, hungry_level: 6, time_available: 45,
  health_goal: 'Normal', diet_preference: 'Mặn', rain_level: 'khong_mua', selected_category: 'all', selected_categories: [], selected_cuisine: 'Tất cả', selected_tastes: [],
  user_lat: DEFAULT_LOCATION.lat, user_lng: DEFAULT_LOCATION.lng, user_label: DEFAULT_LOCATION.label,
  current_time: META.server_time || currentBrowserHHMM(), search_query: ''
};
let lastData = null, restaurantsById = {}, cart = [], cartRestaurant = null, activeOrder = null, trackingTimer = null;
let mainMap = null, mainMarkers = [], mainRoute = null, detailMap = null, detailRoute = null, trackMap = null, trackRoute = null, riderMarker = null;
const $ = (id) => document.getElementById(id);
const money = (n) => new Intl.NumberFormat('vi-VN').format(Math.round(n)) + 'đ';
const escapeHtml = (s) => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const sortRestaurants = (items) => [...(items || [])].sort((a,b) => {
  const ar = Number.isFinite(a.display_rank) ? a.display_rank : null;
  const br = Number.isFinite(b.display_rank) ? b.display_rank : null;
  if(ar !== null && br !== null) return ar - br;
  return ((b.score || 0) - (a.score || 0)) || ((a.distance_km || 999) - (b.distance_km || 999));
});
const rainLabel = (id) => (META.rain_levels || []).find(x => x.id === id)?.label || 'Không mưa';
const categoryLabel = (id) => (META.categories || []).find(x => x.id === id)?.label || id;
const categoryIcon = (id) => (META.categories || []).find(x => x.id === id)?.icon || '🍽️';
const displayName = (r) => r?.display_name || r?.name || 'Quán';
function toast(msg){const t=$('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200)}
function openSheet(id){$(id).classList.add('open')}
function closeSheet(id){$(id).classList.remove('open')}
function switchTab(tab){document.querySelectorAll('.screen').forEach(s=>s.classList.remove('active'));$(tab).classList.add('active');document.querySelectorAll('.nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));if(tab==='map') setTimeout(renderMap,100); if(tab==='orders') renderCart(); if(tab==='profile') renderProfile();}
function imgFallback(img, icon='🍽️'){img.outerHTML = `<div class="food-img" style="display:grid;place-items:center;font-size:42px">${icon}</div>`}

function initControls(){
  const searchEl = $('searchInput');
  searchEl.value = state.search_query || '';
  searchEl.addEventListener('input', e=>{
    state.search_query = e.target.value;
    updateSearchUI();
    renderSearchPanel(state.search_query);
    debouncedSearchRefresh();
  });
  searchEl.addEventListener('focus', ()=>renderSearchPanel(state.search_query));
  searchEl.addEventListener('keydown', e=>{
    if(e.key === 'Enter'){
      e.preventDefault();
      hideSearchPanel();
      refreshRecommendations();
    }
    if(e.key === 'Escape'){
      hideSearchPanel();
    }
  });
  document.addEventListener('click', e=>{
    if(!e.target.closest('.search-wrap')) hideSearchPanel();
  });
  [['budgetRange','total_budget','budgetVal', v=>money(v)], ['peopleRange','group_size','peopleVal', v=>v+' người'], ['hungerRange','hungry_level','hungerVal', v=>v+'/10'], ['deliveryRange','time_available','deliveryVal', v=>v+' phút']].forEach(([input,key,label,fmt])=>{
    $(input).value = state[key]; $(label).textContent = fmt(state[key]);
    $(input).addEventListener('input', e=>{state[key]=Number(e.target.value); $(label).textContent=fmt(state[key]); syncMini(); debouncedNeedsRefresh();});
  });
  $('timeOfDay').value = state.current_time; $('timeOfDay').addEventListener('change', e=>{useRealTime=false; state.current_time=e.target.value || currentBrowserHHMM(); updateClockMode(); debouncedNeedsRefresh();});
  syncLocationLabels(); updateClockMode(); renderChoices(); syncMini(); updateSearchUI(); renderSearchChips();
}
function renderChoices(){
  $('categoryBar').innerHTML = (META.categories||[]).map(c=>`<button class="cat-chip ${c.id==='all'?'all':''} ${isCategoryActive(c.id)?'active':''}" title="${escapeHtml(c.label)}" onclick="selectCategory('${escapeAttr(c.id)}')"><span class="cat-icon">${c.icon}</span><span class="cat-label">${escapeHtml(c.label)}</span></button>`).join('');
  $('categoryChoices').innerHTML = (META.categories||[]).map(c=>`<button class="choice ${isCategoryActive(c.id)?'active':''}" onclick="selectCategory('${escapeAttr(c.id)}', false)">${c.icon} ${c.label}</button>`).join('');
  $('cuisineChoices').innerHTML = (META.cuisines||[]).map(c=>`<button class="choice ${state.selected_cuisine===c?'active':''}" onclick="selectCuisine('${escapeAttr(c)}')">${escapeHtml(c)}</button>`).join('');
  $('tasteChoices').innerHTML = (META.tastes||[]).map(t=>`<button class="choice taste ${state.selected_tastes.includes(t)?'active':''}" onclick="toggleTaste('${escapeAttr(t)}')">${escapeHtml(t)}</button>`).join('');
  $('healthChoices').innerHTML = (META.health_goals||[]).map(h=>`<button class="choice ${state.health_goal===h?'active':''}" onclick="setHealthGoal('${h}')">${h}</button>`).join('');
  const dietCard = $('dietPrefCard');
  if(dietCard){
    dietCard.style.display = state.health_goal === 'Diet' ? 'block' : 'none';
    const prefVal = $('dietPrefVal'); if(prefVal) prefVal.textContent = state.diet_preference;
    const prefs = META.diet_preferences || ['Mặn','Chay'];
    $('dietPreferenceChoices').innerHTML = prefs.map(p=>`<button class="choice ${state.diet_preference===p?'active':''}" onclick="setDietPreference('${p}')">${p === 'Chay' ? 'Ăn chay' : 'Ăn mặn'}</button>`).join('');
  }
  $('rainChoices').innerHTML = (META.rain_levels||[]).map(r=>`<button class="choice ${state.rain_level===r.id?'active':''}" onclick="state.rain_level='${r.id}';renderChoices();syncMini();debouncedNeedsRefresh();">${r.label}</button>`).join('');
}
function scrollActiveCategoryIntoView(){
  const active = document.querySelector('#categoryBar .cat-chip.active:not(.all)') || document.querySelector('#categoryBar .cat-chip.active');
  if(active) active.scrollIntoView({behavior:'smooth', inline:'center', block:'nearest'});
}
function escapeAttr(s){return String(s).replace(/'/g,"\\'")}
function isCategoryActive(id){return id === 'all' ? state.selected_categories.length === 0 : state.selected_categories.includes(id)}
function syncSelectedCategoryCompat(){state.selected_category = state.selected_categories.length === 1 ? state.selected_categories[0] : 'all'}
function selectCategory(id, immediate=true){
  if(id === 'all'){
    state.selected_categories = [];
  }else{
    state.selected_categories = state.selected_categories.includes(id)
      ? state.selected_categories.filter(x => x !== id)
      : [...state.selected_categories, id];
  }
  syncSelectedCategoryCompat();
  renderChoices(); scrollActiveCategoryIntoView(); updateModeBox(); if(immediate) refreshRecommendations();
}
function selectCuisine(c){state.selected_cuisine=c; renderChoices();}
function setHealthGoal(h){
  state.health_goal = h;
  if(h !== 'Diet') state.diet_preference = 'Mặn';
  renderChoices(); syncMini(); debouncedNeedsRefresh();
}
function setDietPreference(p){
  state.diet_preference = p === 'Chay' ? 'Chay' : 'Mặn';
  renderChoices(); syncMini(); debouncedNeedsRefresh();
}
function toggleTaste(t){state.selected_tastes = state.selected_tastes.includes(t) ? state.selected_tastes.filter(x=>x!==t) : [...state.selected_tastes, t]; renderChoices();}
function applyNeeds(){closeSheet('needsSheet'); refreshRecommendations();}
function applyFilters(){closeSheet('filterSheet'); renderChoices(); refreshRecommendations();}
function clearFilters(){state.selected_category='all'; state.selected_categories=[]; state.selected_cuisine='Tất cả'; state.selected_tastes=[]; renderChoices(); refreshRecommendations();}
function debounce(fn,ms){let to; return (...args)=>{clearTimeout(to); to=setTimeout(()=>fn(...args),ms)}}
const debouncedSearchRefresh = debounce(()=>refreshRecommendations(), 350);
const debouncedNeedsRefresh = debounce(()=>refreshRecommendations(), 650);
let searchSuggestSeq = 0;
const DEFAULT_SEARCH_TERMS = ['bún bò','phở','cơm tấm','cơm thố','gà rán','pizza','lẩu','trà sữa','healthy','ăn vặt'];
function updateSearchUI(){
  const clear = $('searchClear');
  if(clear) clear.style.display = state.search_query ? 'grid' : 'none';
}
function hideSearchPanel(){
  const panel = $('searchPanel');
  if(panel) panel.classList.remove('open');
}
function searchTypeIcon(type){
  const t = String(type || '').toLowerCase();
  if(t.includes('quán')) return '🏪';
  if(t.includes('món trong menu') || t === 'món') return '🍽️';
  if(t.includes('nhóm')) return '🏷️';
  if(t.includes('cuisine')) return '🌏';
  if(t.includes('khẩu')) return '😋';
  if(t.includes('địa')) return '📍';
  if(t.includes('popular') || t.includes('gợi')) return '✨';
  return '🔎';
}
function searchSuggestionHTML(label, type, value, sub='Chạm để tìm kiếm'){
  const safeLabel = escapeHtml(label || value || '');
  const safeType = escapeHtml(type || 'Gợi ý');
  const safeValue = escapeAttr(value || label || '');
  const icon = searchTypeIcon(type);
  return `<button class="search-suggestion" onclick="applySearchSuggestion('${safeValue}')">
    <span class="sug-icon">${icon}</span>
    <span class="sug-main">
      <strong class="sug-title">${safeLabel}</strong>
      <span class="sug-sub">${escapeHtml(sub)}</span>
    </span>
    <small class="sug-type">${safeType}</small>
  </button>`;
}
async function renderSearchPanel(query){
  const panel = $('searchPanel');
  if(!panel) return;
  const q = String(query || '').trim();
  if(!q){ panel.classList.remove('open'); panel.innerHTML=''; return; }
  const seq = ++searchSuggestSeq;
  panel.classList.add('open');
  panel.innerHTML = `<button class="search-suggestion loading">
    <span class="sug-icon">🔎</span>
    <span class="sug-main"><strong class="sug-title">Đang tìm gợi ý...</strong><span class="sug-sub">Yeppi đang lọc theo từ khóa</span></span>
    <small class="sug-type">Search</small>
  </button>`;
  try{
    const res = await fetch('/api/search_suggestions?q=' + encodeURIComponent(q));
    const data = await res.json();
    if(seq !== searchSuggestSeq) return;
    const items = (data.suggestions || []).slice(0, 7);
    if(!items.length){
      panel.innerHTML = searchSuggestionHTML(`Tìm “${q}”`, 'Enter', q, 'Không có gợi ý nhanh, bấm để tìm trực tiếp');
      return;
    }
    panel.innerHTML = items.map(s=>searchSuggestionHTML(s.label, s.type || 'Gợi ý', s.value || s.label)).join('');
  }catch(err){
    panel.innerHTML = searchSuggestionHTML(`Tìm “${q}”`, 'Search', q, 'Tìm trực tiếp bằng từ khóa này');
  }
}
function applySearchSuggestion(value){
  state.search_query = value || '';
  const input = $('searchInput'); if(input) input.value = state.search_query;
  updateSearchUI(); hideSearchPanel(); refreshRecommendations();
}
function clearSearchInput(){
  state.search_query = '';
  const input = $('searchInput'); if(input) input.value = '';
  updateSearchUI(); hideSearchPanel(); refreshRecommendations();
}
function renderSearchChips(){
  const box = $('searchChips'); if(!box) return;
  const terms = DEFAULT_SEARCH_TERMS.slice(0, 8);
  box.innerHTML = terms.map(t=>`<button class="search-chip ${state.search_query===t?'active':''}" onclick="applySearchSuggestion('${escapeAttr(t)}')">${escapeHtml(t)}</button>`).join('');
}
function syncMini(){
  $('budgetMini').textContent=money(state.total_budget); $('peopleMini').textContent=state.group_size+' người'; $('timeMini').textContent=state.time_available+' phút';
  $('profileBudget').textContent=money(state.total_budget/Math.max(1,state.group_size)); $('profileHealth').textContent=state.health_goal === 'Diet' ? `${state.health_goal} · ${state.diet_preference}` : state.health_goal; $('profileTime').textContent=state.time_available+' phút'; $('profileRain').textContent=rainLabel(state.rain_level);
  syncLocationLabels(); updateClockMode(); updateModeBox();
}
function syncLocationLabels(){
  const label = state.user_label || DEFAULT_LOCATION.label;
  const userLabel=$('userLabel'); if(userLabel) userLabel.textContent=label;
  const mapLabel=$('mapUserLabel'); if(mapLabel) mapLabel.textContent=label;
  const locationText=$('locationText'); if(locationText) locationText.textContent = `${label} · ${Number(state.user_lat).toFixed(5)}, ${Number(state.user_lng).toFixed(5)}`;
}
function updateClockMode(){
  const clockMode=$('clockMode'); if(clockMode) clockMode.textContent = useRealTime ? 'Thực tế' : 'Tùy chỉnh';
}
function setDeliveryLocation(lat,lng,label){
  state.user_lat = Number(lat); state.user_lng = Number(lng);
  state.user_label = label || `Vị trí hiện tại (${state.user_lat.toFixed(5)}, ${state.user_lng.toFixed(5)})`;
  const status=$('locationStatus'); if(status) status.textContent = label === DEFAULT_LOCATION.label ? 'Mặc định' : 'GPS';
  syncLocationLabels();
  refreshRecommendations();
}
function getCurrentLocation(){
  if(!navigator.geolocation){ toast('Trình duyệt không hỗ trợ lấy vị trí'); return; }
  const status=$('locationStatus'); if(status) status.textContent='Đang lấy...';
  navigator.geolocation.getCurrentPosition(pos=>{
    const lat=pos.coords.latitude, lng=pos.coords.longitude;
    setDeliveryLocation(lat,lng,`Vị trí hiện tại (${lat.toFixed(5)}, ${lng.toFixed(5)})`);
    toast('Đã cập nhật vị trí hiện tại');
  },()=>{
    if(status) status.textContent='Không có quyền';
    toast('Không lấy được vị trí. Hãy cấp quyền GPS hoặc dùng vị trí UEH.');
  },{enableHighAccuracy:true,timeout:12000,maximumAge:60000});
}
function resetDefaultLocation(){
  setDeliveryLocation(DEFAULT_LOCATION.lat, DEFAULT_LOCATION.lng, DEFAULT_LOCATION.label);
  toast('Đã chuyển về UEH cơ sở B');
}
function useCurrentTimeNow(){
  useRealTime = true; state.current_time = currentBrowserHHMM();
  const input=$('timeOfDay'); if(input) input.value = state.current_time;
  updateClockMode(); refreshRecommendations(); toast('Đã dùng giờ hiện tại');
}
function syncRealClock(){
  updateStatusClock();
  if(!useRealTime) return;
  const now=currentBrowserHHMM();
  if(state.current_time !== now){
    state.current_time = now;
    const input=$('timeOfDay'); if(input) input.value = now;
    updateClockMode(); refreshRecommendations();
  }
}
setInterval(syncRealClock, 60000);
function updateModeBox(){
  const has = state.selected_categories.length || state.selected_cuisine!=='Tất cả' || state.selected_tastes.length;
  $('smartTitle').textContent = has ? 'Bạn đã có gu rồi?' : 'Để Yeppi lo!';
  $('smartText').textContent = has ? 'Yeppi ưu tiên món bạn chọn, rồi gợi ý quán vừa túi tiền và giao kịp giờ.' : 'Gợi ý món phù hợp với khẩu vị, ngân sách và thời gian của bạn.';
  $('modeBox').innerHTML = `<div class="info-icon">${has?'🎯':'✨'}</div><div><h4>${has?'Đang ưu tiên lựa chọn của bạn':'Để Yeppi chọn giúp'}</h4><p>${has?'Kết quả được sắp theo nhóm món, giá, khoảng cách và thời gian giao.':'Bạn có thể chọn nhanh một nhóm món hoặc xem ngay các gợi ý bên dưới.'}</p></div>`;
}
async function refreshRecommendations(){
  if(bootError) return;
  $('resultList').innerHTML='<div class="loader pulse">Đang tìm quán phù hợp...</div>'; $('warningBox').innerHTML='';
  const res = await fetch('/api/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});
  const data = await res.json();
  if(!data.ok){$('resultList').innerHTML=`<div class="empty">${escapeHtml(data.error || 'Có lỗi xảy ra')}</div>`;return}
  data.restaurants = sortRestaurants(data.restaurants || []);
  lastData=data; restaurantsById = {}; data.restaurants.forEach(r=>restaurantsById[r.id]=r);
  renderResults(); renderMapList(); renderProfile(); updateModeBox(); renderSearchChips();
}
function renderResults(){
  if(!lastData) return; const items=sortRestaurants(lastData.restaurants || []);
  const searchText = lastData.search_active ? ` · tìm “${lastData.search_query}”` : '';
  $('resultSub').textContent=`${items.length} quán · trong ${lastData.effective_max_distance_km}km · ${lastData.current_time}${searchText}`;
  $('warningBox').innerHTML = lastData.warning ? `<div class="alert">${escapeHtml(lastData.warning)} ${lastData.fallback_steps?.length?' · '+escapeHtml(lastData.fallback_steps.join(' → ')):''}</div>` : '';
  $('explainBox').innerHTML = `<div class="info-icon">🧠</div><div><h4>Vì sao app gợi ý như vậy?</h4><p>${escapeHtml(lastData.summary)}</p></div>`;
  if(!items.length){
    const q = lastData.search_query ? ` cho “${escapeHtml(lastData.search_query)}”` : '';
    $('resultList').innerHTML=`<div class="empty">Không có kết quả${q}. Hãy thử từ khóa khác, bỏ bớt lọc, tăng ngân sách hoặc đổi giờ đặt.</div>`;return}
  $('resultList').innerHTML=items.map(cardHtml).join('');
}
function cardHtml(r){return `<div class="rest-card" onclick="openDetail('${escapeAttr(r.id)}')"><div class="rest-main"><img class="food-img" src="${r.image}" onerror="imgFallback(this,'${r.icon}')"><div style="flex:1;min-width:0"><div class="rest-title-row"><div><div class="rest-name">${escapeHtml(displayName(r))}</div><div class="rest-sub">${escapeHtml(r.address)}</div></div><div class="score-badge">${r.score_percent}%</div></div><div class="meta-row"><span class="tag">⭐ ${r.rating ?? 'N/A'}</span><span class="tag">🛵 ${r.delivery_range.text}</span><span class="tag">📍 ${r.distance_km}km</span></div><div class="meta-row"><span class="tag">${r.icon} ${escapeHtml(r.primary_label)}</span>${r.search_match_label?`<span class="tag">🔎 ${escapeHtml(r.search_match_label)}</span>`:''}${(r.cuisines||[]).slice(0,2).map(c=>`<span class="tag">${escapeHtml(c)}</span>`).join('')}${r.diet_type?`<span class="tag">${escapeHtml(r.diet_type)}</span>`:''}</div><div class="price-row"><span class="price">${escapeHtml(r.price_text)}</span><button class="add-btn" onclick="event.stopPropagation();quickAdd('${escapeAttr(r.id)}')">＋</button></div></div></div><div class="reason"><b style="color:var(--orange)">Vì sao gợi ý:</b> ${escapeHtml((r.reasons||[]).join(', '))}.</div></div>`}
function renderMapList(){if(!lastData)return; $('mapList').innerHTML=sortRestaurants(lastData.restaurants||[]).slice(0,5).map(r=>cardHtml(r)).join('') || '<div class="empty">Chưa có quán để hiển thị trên map.</div>'}
function initLeafletMap(el){const map=L.map(el,{zoomControl:false}); L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap'}).addTo(map); return map;}
function divIcon(cls, html){return L.divIcon({className:'',html:`<div class="map-pin ${cls||''}">${html}</div>`,iconSize:[34,34],iconAnchor:[17,17]})}
function renderMap(){
  if(!lastData) return; if(!mainMap) mainMap=initLeafletMap('mainMap'); mainMarkers.forEach(m=>m.remove()); mainMarkers=[]; if(mainRoute){mainRoute.remove(); mainRoute=null}
  const user=[state.user_lat,state.user_lng]; mainMarkers.push(L.marker(user,{icon:divIcon('user-pin','📍')}).addTo(mainMap).bindPopup('Vị trí của bạn'));
  const bounds=[user]; sortRestaurants(lastData.restaurants||[]).forEach(r=>{const m=L.marker([r.lat,r.lng],{icon:divIcon('',r.icon)}).addTo(mainMap).bindPopup(`<b>${escapeHtml(displayName(r))}</b><br>${r.distance_km}km · ${r.delivery_range.text}`); m.on('click',()=>focusRoute(r.id)); mainMarkers.push(m); bounds.push([r.lat,r.lng]);});
  if(bounds.length>1) mainMap.fitBounds(bounds,{padding:[25,25]}); else mainMap.setView(user,14);
}
async function focusRoute(id){const r=restaurantsById[id]; if(!r||!mainMap)return; const res=await fetch(`/api/route/${id}?user_lat=${state.user_lat}&user_lng=${state.user_lng}`); const data=await res.json(); if(!data.ok)return; if(mainRoute) mainRoute.remove(); mainRoute=L.polyline(data.route.points,{weight:5,opacity:.85,color:'#28c7b8'}).addTo(mainMap); mainMap.fitBounds(mainRoute.getBounds(),{padding:[30,30]});}
async function openDetail(id){
  const r=restaurantsById[id]; if(!r)return; const modal=$('detailModal');
  modal.innerHTML=`<div class="detail-scroller"><button class="back" onclick="closeDetail()">←</button><div class="hero"><img src="${r.image}" onerror="this.style.display='none'"></div><div class="detail-body"><div class="detail-card"><h2>${escapeHtml(displayName(r))}</h2><p class="rest-sub" style="max-width:100%;margin-top:7px">${escapeHtml(r.address)}</p><div class="metrics"><div class="metric"><b>⭐ ${r.rating ?? 'N/A'}</b><small>Rating</small></div><div class="metric"><b>${r.distance_km}km</b><small>Đường đi</small></div><div class="metric"><b>${r.delivery_range.text}</b><small>ETA</small></div></div><div class="meta-row"><span class="tag">${r.icon} ${escapeHtml(r.primary_label)}</span>${(r.cuisines||[]).map(c=>`<span class="tag">${escapeHtml(c)}</span>`).join('')}${(r.tastes||[]).map(t=>`<span class="tag">${escapeHtml(t)}</span>`).join('')}<span class="tag">${escapeHtml(r.diet_type || 'Mặn')}</span><span class="tag">Protein ${escapeHtml(r.protein_level || 'Medium')}</span><span class="tag">${escapeHtml(r.portion_size || 'Medium')}</span></div><div class="reason"><b style="color:var(--orange)">Lý do hợp với bạn:</b> ${escapeHtml((r.reasons||[]).join(', '))}.</div></div><div class="section-title"><div><h2>Đường giao hàng</h2><p>Từ quán đến địa chỉ giao</p></div></div><div id="detailMap" class="route-map"></div><div class="section-title"><div><h2>Món nổi bật</h2><p>${escapeHtml(r.price_text)}</p></div></div><div>${(r.menu||[]).map(m=>`<div class="menu-item"><img src="${m.image}" onerror="imgFallback(this,'${r.icon}')"><div class="menu-info"><h4>${escapeHtml(m.name)}</h4><b style="color:var(--orange)">${money(m.price)}</b></div><button class="add-btn" onclick="addToCart('${escapeAttr(r.id)}','${escapeAttr(m.id)}')">＋</button></div>`).join('')}</div></div></div>`;
  modal.classList.add('open'); setTimeout(()=>renderDetailRoute(id),120);
}
function closeDetail(){ $('detailModal').classList.remove('open'); $('detailModal').innerHTML=''; detailMap=null; detailRoute=null; }
async function renderDetailRoute(id){const r=restaurantsById[id]; if(!r)return; detailMap=initLeafletMap('detailMap'); const res=await fetch(`/api/route/${id}?user_lat=${state.user_lat}&user_lng=${state.user_lng}`); const data=await res.json(); L.marker([r.lat,r.lng],{icon:divIcon('',r.icon)}).addTo(detailMap); L.marker([state.user_lat,state.user_lng],{icon:divIcon('user-pin','📍')}).addTo(detailMap); if(data.ok){detailRoute=L.polyline(data.route.points,{weight:5,color:'#28c7b8'}).addTo(detailMap); detailMap.fitBounds(detailRoute.getBounds(),{padding:[20,20]});}else detailMap.setView([r.lat,r.lng],14)}
function quickAdd(id){const r=restaurantsById[id]; if(r?.menu?.[0]) addToCart(id,r.menu[0].id)}
function addToCart(rid, mid){const r=restaurantsById[rid]; const m=(r.menu||[]).find(x=>x.id===mid); if(!r||!m)return; if(cartRestaurant && cartRestaurant.id!==rid){ if(!confirm('Giỏ hàng đang có món từ quán khác. Xóa giỏ cũ?')) return; cart=[]; } cartRestaurant=r; const found=cart.find(x=>x.id===mid); if(found) found.qty++; else cart.push({...m,qty:1}); updateCartCount(); toast('Đã thêm vào giỏ'); renderCart();}
function updateCartCount(){const n=cart.reduce((s,x)=>s+x.qty,0); $('cartCount').style.display=n?'grid':'none'; $('cartCount').textContent=n;}
function renderCart(){
  const box=$('cartBox'); const tracking=$('trackingBox'); updateCartCount();
  if(!cart.length){box.innerHTML='<div class="empty" style="margin-top:16px">🛒<h3>Giỏ hàng đang trống</h3><p>Chọn món từ các quán được gợi ý để checkout.</p></div>'; tracking.innerHTML=''; return;}
  const subtotal=cart.reduce((s,x)=>s+x.price*x.qty,0); const fee=15000;
  box.innerHTML=`<div class="summary-card"><h3 style="margin:0 0 10px">${escapeHtml(displayName(cartRestaurant))}</h3>${cart.map(x=>`<div class="cart-line"><div><b>${escapeHtml(x.name)}</b><br><span style="font-size:12px;color:var(--orange);font-weight:900">${money(x.price)}</span></div><div class="qty"><button onclick="changeQty('${escapeAttr(x.id)}',-1)">−</button><b>${x.qty}</b><button onclick="changeQty('${escapeAttr(x.id)}',1)">+</button></div></div>`).join('')}<div class="summary-line"><span>Tạm tính</span><b>${money(subtotal)}</b></div><div class="summary-line"><span>Phí giao dự kiến</span><b>${money(fee)}</b></div><div class="summary-line" style="border-top:1px solid var(--line);padding-top:10px"><span>Tổng</span><b style="color:var(--orange);font-size:18px">${money(subtotal+fee)}</b></div><button class="primary-btn" style="width:100%;margin-top:10px" onclick="checkout()">Đặt món & theo dõi</button></div>`;
  if(activeOrder) renderTrackingBox(activeOrder);
}
function changeQty(id,delta){const it=cart.find(x=>x.id===id); if(!it)return; it.qty+=delta; if(it.qty<=0) cart=cart.filter(x=>x.id!==id); if(!cart.length) cartRestaurant=null; renderCart();}
async function checkout(){ if(!cartRestaurant)return; const res=await fetch('/api/create_order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({restaurant_id:cartRestaurant.id,items:cart,user_lat:state.user_lat,user_lng:state.user_lng,estimated_delivery_min:cartRestaurant.estimated_delivery_min})}); const data=await res.json(); if(!data.ok){toast(data.error||'Không tạo được đơn');return} activeOrder=data.order; renderTrackingBox(activeOrder); startTracking(); toast('Đã đặt món. Tracking đang chạy.');}
function renderTrackingBox(order){$('trackingBox').innerHTML=`<div class="tracking-card"><div style="display:flex;justify-content:space-between;align-items:center"><h3 style="margin:0">Đơn ${order.id}</h3><span class="score-badge" style="background:rgba(255,255,255,.12);color:#fff">ETA còn <b id="etaLeft">${order.eta_left_min}</b> phút</span></div><p style="font-size:12px;color:rgba(255,255,255,.62);line-height:1.5">Đơn đang được giao đến ${escapeHtml(state.user_label || DEFAULT_LOCATION.label)}.</p><div id="trackMap" class="track-map"></div><div class="timeline" id="timeline"></div></div>`; setTimeout(()=>renderTrackMap(order),80); updateTimeline(order);}
function updateTimeline(order){const steps=['Quán xác nhận','Đang chuẩn bị','Tài xế đang giao','Đã giao đến bạn']; $('timeline').innerHTML=steps.map((s,i)=>`<div class="step ${i<=order.stage_index?'active':''}"><div class="dot">${i<order.stage_index?'✓':i+1}</div>${s}</div>`).join(''); const eta=$('etaLeft'); if(eta) eta.textContent=order.eta_left_min;}
function renderTrackMap(order){ if(!$('trackMap'))return; trackMap=initLeafletMap('trackMap'); L.marker([order.restaurant.lat,order.restaurant.lng],{icon:divIcon('',order.restaurant.icon)}).addTo(trackMap); L.marker([state.user_lat,state.user_lng],{icon:divIcon('user-pin','📍')}).addTo(trackMap); trackRoute=L.polyline(order.route.points,{weight:5,color:'#28c7b8'}).addTo(trackMap); riderMarker=L.marker([order.courier.lat,order.courier.lng],{icon:divIcon('rider-pin','🛵')}).addTo(trackMap); trackMap.fitBounds(trackRoute.getBounds(),{padding:[20,20]});}
function startTracking(){ if(trackingTimer) clearInterval(trackingTimer); trackingTimer=setInterval(async()=>{if(!activeOrder)return; const res=await fetch('/api/tracking/'+activeOrder.id); const data=await res.json(); if(!data.ok)return; activeOrder=data.order; updateTimeline(activeOrder); if(riderMarker) riderMarker.setLatLng([activeOrder.courier.lat,activeOrder.courier.lng]); if(activeOrder.progress>=1){clearInterval(trackingTimer);toast('Đơn đã được giao!')}} ,1300);}
function renderProfile(){syncMini(); $('profileTastes').innerHTML=(state.selected_tastes.length?state.selected_tastes:['Chưa chọn']).map(t=>`<span class="tag">${escapeHtml(t)}</span>`).join('')}
window.addEventListener('load',()=>{updateStatusClock(); initControls(); refreshRecommendations();});
</script>
</body>
</html>
'''




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
