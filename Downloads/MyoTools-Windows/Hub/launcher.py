#!/usr/bin/env python3
"""MyoTools Hub: local landing page for two isolated Conda/Voila environments.
This file uses Python standard library only.
"""
from __future__ import annotations
import atexit, html, json, os, secrets, shutil, socket, subprocess, sys, threading, time, webbrowser
from urllib.request import urlopen
from urllib.error import URLError
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote
from app_registry import load_tools
from installation import CONFIRMATION
import model_manager
import uninstall as uninstaller
import updater
import update_page
import update_service

ROOT = Path(__file__).resolve().parent.parent
ON_WINDOWS = os.name == "nt"
MODE = "development" if "--dev" in sys.argv or "--development" in sys.argv else ("release" if "--release" in sys.argv else None)
TOOLS, MODE = load_tools(ROOT, mode=MODE)
APPS = {item.id: item for item in TOOLS}
LOCK = threading.RLock()
RUNNING = {}
UNINSTALLING = False
UNINSTALL_TOKEN = secrets.token_urlsafe(32)
MODEL_TOKEN = secrets.token_urlsafe(32)
MODEL_LOCK = threading.Lock()
UPDATE_LOCK = threading.Lock()
UPDATE_TOKEN = secrets.token_urlsafe(32)
UPDATE_SHUTDOWN = False

def conda_command():
    saved = ROOT / "Hub" / "runtime" / "conda_path.txt"
    stored = saved.read_text(encoding="utf-8").strip() if saved.is_file() else None
    candidates = [stored, os.environ.get("CONDA_EXE"), os.environ.get("MYOTOOLS_CONDA_EXE"), shutil.which("conda")]
    for base in ("miniforge3", "miniconda3", "anaconda3"):
        basepath = Path.home() / base
        candidates.extend([str(basepath / "Scripts" / "conda.exe"), str(basepath / "bin" / "conda")])
    for cmd in candidates:
        if cmd and Path(cmd).is_file():
            return str(Path(cmd).resolve())
    return None

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

def alive(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False

def voila_responding(port):
    """Check that Voila serves HTTP, not merely that a TCP port is open.

    This checks a small endpoint rather than rendering a notebook a second time.
    """
    try:
        with urlopen("http://127.0.0.1:%d/" % port, timeout=1.5) as response:
            return response.status < 500
    except Exception:
        return False

def backend_url(item, port):
    # All notebook URLs are resolved from the package root.
    return "http://127.0.0.1:%s/voila/render/%s" % (port, quote(item.notebook, safe="/"))

def stop():
    for record in list(RUNNING.values()):
        process = record["process"]
        if process.poll() is None:
            try:
                if ON_WINDOWS:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], timeout=8,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    import signal
                    os.killpg(process.pid, signal.SIGTERM)
            except (OSError, subprocess.SubprocessError):
                pass
    RUNNING.clear()
atexit.register(stop)

def required_files(item):
    items = [ROOT / item.notebook]
    if item.error:
        return [item.error]
    if item.id == "myoclass":
        items.append(ROOT / "MyoClass/Corrections_napari_MyoClass.py")
    return [str(f.relative_to(ROOT)) for f in items if not f.is_file()]

def status(item):
    missing = required_files(item)
    if missing:
        return {"state":"missing", "message":"Missing: "+", ".join(missing), "version":item.version}
    rec = RUNNING.get(item.id)
    if rec:
        if rec["process"].poll() is not None:
            try: detail = rec["log"].read_text(errors="replace")[-2500:]
            except OSError: detail = ""
            return {"state":"error", "message":"Voila stopped: "+detail}
        if voila_responding(rec["port"]):
            return {"state":"running", "message":"Launched", "url":backend_url(item,rec["port"])}
        return {"state":"starting", "message":"Starting the notebook server..."}
    note = " · Svetlana model not installed (select or install it in MyoFuse)" if item.id == "myofuse" and not (ROOT / "MyoFuse/Models/Svetlana/MyoFuse.pth").is_file() else ""
    return {"state":"available","message":"v"+str(item.version)+" · Launch in "+item.environment+note, "version":item.version}

def start(item):
    with LOCK:
        if UNINSTALLING or UPDATE_SHUTDOWN:
            raise RuntimeError("MyoTools maintenance is starting. Close the hub and wait for restart.")
        missing = required_files(item)
        if missing:
            raise RuntimeError("Missing files: "+", ".join(missing)+". Run the installer.")
        group = item.environment
        if item.id in RUNNING and RUNNING[item.id]["process"].poll() is None:
            return status(item)
        conda = conda_command()
        if not conda:
            raise RuntimeError("Conda not found. Run Hub/platforms/windows/install.bat or Hub/platforms/linux/install.sh.")
        port = free_port()
        log_dir = ROOT / "Hub" / "runtime"
        log_dir.mkdir(exist_ok=True)
        log = log_dir / (item.id+".log")
        cmd = [conda,"run","--no-capture-output","-n",group,"python","-m","voila",
               "--no-browser", "--port=%d" % port,"--Voila.ip=127.0.0.1"]
        # The notebooks live under ROOT, and Voila serves only the files in this folder.
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if ON_WINDOWS else 0
        env = {**os.environ, "MYOTOOLS_MODEL_DIR": str(model_manager.MODEL_DIR)}
        with log.open("w",encoding="utf-8") as f:
            proc = subprocess.Popen(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,
                                    creationflags=flags,start_new_session=not ON_WINDOWS,env=env)
        RUNNING[item.id]={"process":proc,"port":port,"log":log}
        return status(item)

STYLE = """
:root{--ink:#131039;--muted:#6c6a98;--purple:#7951eb;--purple2:#9263e8;--bg:#ffffff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,'Segoe UI',Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:inherit}
.top{width:min(1600px,96%);margin:0 auto;padding:20px 18px 26px;display:flex;align-items:center;gap:17px}
.mark{width:44px;height:44px;flex-shrink:0;display:grid;place-items:center;border-radius:12px;background:linear-gradient(135deg,#9868ec,#7850e9);color:#fff;font-size:22px;font-weight:800;letter-spacing:-1px;line-height:1}
.brand{font-size:30px;font-weight:800;letter-spacing:-1.1px;text-decoration:none}
.subtitle{margin-left:8px;border-left:1px solid #bcb0d4;padding-left:22px;color:#444176;font-size:16px}
.top{flex-wrap:wrap}
.top-links{margin-left:auto;display:flex;align-items:center;justify-content:flex-end;gap:10px}
.top-link{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;text-decoration:none;color:#54427e;font-size:14px;font-weight:650;padding:10px 14px;border-radius:11px;border:1px solid #e7dff7;background:#fbfaff;transition:background .2s,border-color .2s}
.top-link:hover{background:#f0eaff;border-color:#cdbbf4;color:#5431b5}
.top-link:focus-visible{outline:3px solid #7951eb;outline-offset:3px}
.version-pill{padding:8px 11px;border-radius:10px;background:#f2edff;color:#6440b2;font-size:12px;font-weight:700;white-space:nowrap}
.top-link svg{display:block;width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;flex:none}

main{width:min(1600px,96%);margin:0 auto 48px;display:grid;gap:18px}
.band{min-height:415px;display:grid;grid-template-columns:34% 66%;overflow:hidden;position:relative;border-radius:18px;background:#f3f1ff}
.band:before{content:'';position:absolute;inset:0;pointer-events:none}
.band.invivo:before{background:linear-gradient(90deg,#f2f2ff 0%,#f1f0ff 42%,rgba(247,235,255,.55) 73%,rgba(248,226,255,.2)),url('/assets/microscopy-sprite.webp');background-size:cover,200% 300%;background-position:center,100% 50%;opacity:.96}
.band.invitro:before{background:linear-gradient(90deg,rgba(245,243,255,.95),rgba(243,238,255,.67) 50%,#f1f0ff 88%),url('/assets/microscopy-sprite.webp');background-size:cover,200% 300%;background-position:center,100% 100%}
.band>*{position:relative;z-index:1}
.band-copy{padding:65px 5% 45px 7%;display:flex;justify-content:center;flex-direction:column}
.tick{width:48px;height:4px;border-radius:4px;background:#8157ed;margin:0 0 23px}
.band h1{font-size:clamp(48px,5.25vw,78px);letter-spacing:-3.4px;line-height:1.07;margin:0 0 22px;font-weight:800}
.band-copy p{color:#666694;font-size:clamp(15px,1.38vw,21px);line-height:1.53;margin:0;max-width:400px}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;align-content:center;padding:35px 4.3% 35px 0}
.card{background:rgba(255,255,255,.96);border:1px solid rgba(255,255,255,.88);border-radius:20px;box-shadow:0 12px 26px rgba(57,35,105,.075);padding:22px;min-width:0;transition:transform .2s,box-shadow .2s}
.card:hover{transform:translateY(-3px);box-shadow:0 18px 38px rgba(57,35,105,.14)}
.card-head{display:flex;gap:17px;align-items:center;margin-bottom:14px;min-height:72px}
.tool-icon{width:67px;height:67px;border-radius:16px;flex:none;display:grid;place-items:center;background:linear-gradient(135deg,#996ce7,#7345e8);color:white}
.tool-icon svg{width:46px;height:46px}
.tool-icon.myoseg{background:linear-gradient(125deg,#080808,#151515 67%,#252525)}
.tool-icon.myoclass{background:linear-gradient(125deg,#310b13,#6c1426 67%,#9a2039)}
.tool-icon.myofuse{background:linear-gradient(125deg,#24163f,#382064 67%,#542d91)}
.tool-icon.myosurface{background:linear-gradient(125deg,#081f4c,#0c387b 67%,#1656b4)}
.card-title{flex:1;min-width:0}
.card h2{font-size:23px;letter-spacing:-.7px;margin:0 0 5px}
.card .detail{font-size:14px;color:var(--muted);line-height:1.3;margin:0}
.chevron{font-size:30px;color:#8354ed;align-self:flex-start}
.preview{width:100%;aspect-ratio:2.5/1;object-fit:cover;border-radius:11px;background-image:url('/assets/microscopy-sprite.webp');background-size:200% 300%;background-repeat:no-repeat}
.preview.myoseg{background-position:0 0}.preview.myoclass{background-position:100% 0}
.preview.myofuse{background-position:0 50%}.preview.myosurface{background-position:100% 50%}
.card-bottom{margin-top:13px;display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.open{display:inline-flex;align-items:center;justify-content:center;gap:12px;background:linear-gradient(110deg,#9568ed,#7950e8);border-radius:10px;text-decoration:none;color:white;font-size:15px;font-weight:600;padding:12px 25px;min-height:43px;white-space:nowrap}
.open:hover,.open:focus-visible{background:linear-gradient(110deg,#7e54e3,#633ad3)}
.state{font-size:11px;color:#716984;line-height:1.2;text-align:right;max-width:150px;overflow-wrap:anywhere}
.foot{width:min(1600px,96%);padding:0 18px 24px;margin:auto;color:#918baa;font-size:12px}
@media (max-width:1170px){.band{grid-template-columns:31% 69%}.band-copy{padding:35px 5%}.cards{padding:27px 20px 27px 0}.card{padding:15px}.tool-icon{width:55px;height:55px}.tool-icon svg{width:38px;height:38px}.card h2{font-size:19px}.detail{font-size:12px!important}.state{display:none}}
@media (max-width:860px){.band{grid-template-columns:1fr;min-height:auto}.band-copy{padding:36px 35px 14px}.band h1{font-size:53px}.band-copy p{max-width:600px}.cards{padding:15px 25px 30px}.band:before{opacity:.75}}
@media (max-width:550px){.top{padding:20px 3px;gap:10px}.top-links{width:100%;margin-left:0;gap:8px}.top-link{font-size:12px;padding:8px 12px}.mark{width:37px;height:37px;border-radius:10px;font-size:19px}.brand{font-size:24px}.subtitle{font-size:11px;margin-left:0;padding-left:12px}.band-copy{padding:27px 22px 12px}.band h1{font-size:44px;margin-bottom:12px}.cards{grid-template-columns:1fr;padding:15px}.card{padding:17px}.card h2{font-size:21px}.card .detail{font-size:14px!important}.preview{aspect-ratio:2.8/1}}
@media (prefers-reduced-motion:reduce){.card{transition:none}}
"""
def _tool_icon(key):
    """Application initials in the existing square badges."""
    initials = {"myofuse": "MF", "myoseg": "MSg", "myosurface": "MSf", "myoclass": "MC"}.get(key, "MT")
    font_size = "29" if len(initials) == 3 else "38"
    return ('<svg viewBox="0 0 64 64" aria-hidden="true">'
            '<text x="32" y="33" text-anchor="middle" dominant-baseline="central" '
            'font-family="Arial,sans-serif" font-size="' + font_size + '" font-weight="700" '
            'letter-spacing="-1" fill="currentColor">' + initials + '</text></svg>')


def homepage():
    tool_cards = {}
    for item in TOOLS:
        st = status(item)
        key = html.escape(item.id)
        version = html.escape(item.version or "unavailable")
        label = html.escape(st["message"])
        tool_cards[item.id] = (
            '<article class="card"><div class="card-head"><div class="tool-icon ' + key + '" aria-hidden="true">' +
            _tool_icon(item.id) + '</div><div class="card-title"><h2>' + html.escape(item.name) +
            '</h2><p class="detail">' + html.escape(item.description) +
            '</p></div><span class="chevron" aria-hidden="true">›</span></div>' +
            '<div class="preview ' + key + '" role="img" aria-label="Microscopy illustration for ' +
            html.escape(item.name) + '"></div><div class="card-bottom">' +
            '<a class="open" href="/launch/' + key + '" aria-label="Open ' +
            html.escape(item.name) + '">Open tool <span aria-hidden="true">→</span></a>' +
            '<span class="state" id="s-' + key + '" title="v' + version + '">' + label +
            '</span></div></article>'
        )
    sections = [
        ('invivo', 'In vivo', 'Tools for skeletal muscle analysis in intact tissue, from fiber segmentation to fiber typing.', ['myoseg','myoclass']),
        ('invitro', 'In vitro', 'Tools for cell culture and myotube analysis, from fusion quantification to surface measurement.', ['myofuse','myosurface'])
    ]
    bands = []
    for cls, title, description, ids in sections:
        cards = ''.join(tool_cards[k] for k in ids if k in tool_cards)
        bands.append('<section class="band ' + cls + '" aria-label="' + title +
                     '"><div class="band-copy"><span class="tick" aria-hidden="true"></span><h1>' +
                     title + '</h1><p>' + description + '</p></div><div class="cards">' +
                     cards + '</div></section>')
    logo = '<span class="mark" aria-hidden="true">MT</span>'
    return ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#ffffff">
<title>MyoTools | Muscle image analysis suite</title><style>""" + STYLE +
"""</style></head><body><header class="top">""" + logo +
'<a class="brand" href="/">MyoTools</a><span class="subtitle">Muscle microscopy analysis suite</span>' +
    '<span class="version-pill">v' + html.escape(updater.current_version(ROOT)) + ' · ' + html.escape("STABLE" if updater.current_channel(ROOT) == "main" else "INTERNAL") + '</span>' +
'<nav class="top-links" aria-label="Project links">' +
'<a class="top-link" href="/updates">Check for updates</a>' +
    '<a class="top-link" href="/models">Models</a>' +
'<a class="top-link" href="https://github.com/' + html.escape(updater.REPO, quote=True) + '" target="_blank" rel="noopener noreferrer" aria-label="MyoTools repository on GitHub">' +
'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 19c-4.3 1.4-4.3-2.4-6-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 5.77 5.07 5.07 0 0 0 19.91 2S18.73 1.65 16 4.48a13.38 13.38 0 0 0-7 0C6.27 1.65 5.09 2 5.09 2A5.07 5.07 0 0 0 5 5.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 19.13V22"/></svg>' +
'GitHub</a>' +
'<a class="top-link" href="mailto:lair.b1jamin@gmail.com?subject=MyoTools%20contact" aria-label="Contact the MyoTools developer by email" title="lair.b1jamin@gmail.com">' +
'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>' +
'Contact</a></nav></header>' +
'<main>' + ''.join(bands) + '</main><footer class="foot">MyoTools · Local microscopy analysis · <a href="/uninstall">Uninstall MyoTools</a></footer>' +
"""<script>
async function refresh(){
 try{
  const r=await fetch('/api/status',{cache:'no-store'});
  if(!r.ok)return;
  const data=await r.json();
  for(const [key,item] of Object.entries(data)){
   const el=document.getElementById('s-'+key);
   if(el)el.textContent=item.state==='available'?'v'+(item.version||'?')+' · Ready':item.state==='running'?'Launched':item.message;
  }
 }catch(_){}
}
refresh();setInterval(refresh,3500);
</script></body></html>""")

def launchpage(key):
    item = APPS[key]
    safe_key = json.dumps(item.id)
    name = html.escape(item.name)
    icon = _tool_icon(item.id)
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Launching TOOL_NAME | MyoTools</title><style>
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif;color:#201740}
*{box-sizing:border-box}
body{margin:0;background:#f9f7ff;min-height:100vh;display:grid;place-items:center;padding:25px}
.load-card{background:white;border:1px solid #ece5fa;border-radius:24px;box-shadow:0 30px 80px rgba(66,39,145,.1);padding:46px 46px 36px;text-align:center;max-width:540px;width:100%}
.logo{font-size:20px;font-weight:800;letter-spacing:-.5px;color:#30205f;margin-bottom:35px}
.logo b{color:#8359e9}
.app-icon{width:82px;height:82px;display:grid;place-items:center;margin:0 auto 22px;border-radius:22px;background:linear-gradient(135deg,#9e71ef,#7145e6);color:#fff}
.app-icon svg{width:56px;height:56px}
h1{font-size:29px;letter-spacing:-.8px;margin:0 0 9px}
.subtitle{font-size:14px;color:#81799d;margin:0 0 31px}
.progress{width:100%;height:7px;background:#eee9fa;border-radius:20px;overflow:hidden;position:relative}
.progress:after{content:"";position:absolute;inset:0;width:35%;background:linear-gradient(90deg,#b89cf7,#754bea);border-radius:20px;animation:travel 1.8s ease-in-out infinite alternate}
@keyframes travel{from{left:0}to{left:65%}}
#msg{font-size:13px;color:#685792;margin:17px auto 0;min-height:19px}
#err{display:none;background:#fff1f3;border-radius:10px;padding:15px;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere;color:#8d2745;font-size:12px;max-height:170px;overflow:auto}
#retry{display:none;border:0;background:#7951eb;color:white;border-radius:9px;padding:12px 22px;font-weight:650;cursor:pointer}
.back{display:inline-block;margin-top:27px;color:#7951eb;text-decoration:none;font-size:13px;font-weight:650}
@media(max-width:560px){.load-card{padding:32px 20px}h1{font-size:24px}}
@media(prefers-reduced-motion:reduce){.progress:after{animation:none;width:100%}}
</style></head><body><main class="load-card" role="status" aria-live="polite">
<div class="logo"><b>◈</b> MyoTools</div>
<div class="app-icon">TOOL_ICON</div>
<h1>Launching TOOL_NAME</h1>
<p class="subtitle">Preparing your analysis workspace</p>
<div class="progress" id="bar"></div>
<p id="msg">Starting the Voilà server…</p>
<pre id="err"></pre><button id="retry" type="button">Try again</button>
<a class="back" href="/">← Back to MyoTools</a>
</main><script>
const tool=TOOL_KEY;
const sleep=(ms)=>new Promise(resolve=>setTimeout(resolve,ms));
const message=document.getElementById("msg");
async function run(){
 document.getElementById("err").style.display="none";
 document.getElementById("retry").style.display="none";
 document.getElementById("bar").style.display="block";
 message.textContent="Starting the Voilà server…";
 try{
  const response=await fetch("/api/start/"+tool,{method:"POST",cache:"no-store"});
  const result=await response.json();
  if(!response.ok)throw Error(result.error||"Could not start the application");
  let count=0;
  while(count++<180){
   const r=await fetch("/api/status",{cache:"no-store"});
   if(!r.ok)throw Error("Cannot contact MyoTools Hub");
   const states=await r.json();
   const state=states[tool];
   if(!state)throw Error("Application status unavailable");
   if(state.state==="running"){message.textContent="Opening notebook…";window.location.replace(state.url);return;}
   if(state.state==="error"||state.state==="missing")throw Error(state.message);
   message.textContent=count>5?"Loading Voilà and notebook services…":"Initializing analysis environment…";
   await sleep(1000);
  }
  throw Error("Startup timed out after 3 minutes. Check Hub/runtime logs.");
 }catch(error){
  message.textContent="Unable to start TOOL_NAME";
  document.getElementById("bar").style.display="none";
  const errorBox=document.getElementById("err");
  errorBox.textContent=String(error);errorBox.style.display="block";
  document.getElementById("retry").style.display="inline-block";
 }
}
document.getElementById("retry").addEventListener("click",run);
run();
</script></body></html>"""
    return page.replace("TOOL_KEY", safe_key).replace("TOOL_NAME", name).replace("TOOL_ICON", icon)


def modelspage():
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Models | MyoTools</title><style>""" + STYLE + """
.models{display:block;max-width:900px;padding:28px}
.models h1{margin:28px 0 9px}.models p{line-height:1.55;color:#544c72}
.model{border:1px solid #e7dff7;border-radius:16px;padding:18px;margin:14px 0;background:#fff}
.model h2{margin:0 0 7px;font-size:19px}.model p{margin:5px 0}.model code{overflow-wrap:anywhere}
.model button{border:0;cursor:pointer;margin:10px 0 0}.model button:disabled{opacity:.55;cursor:default}
.model a{color:#6843cf}.model .feedback{color:#603fa6;overflow-wrap:anywhere}
</style></head><body><main class="models"><a href="/">← Back to MyoTools</a>
<h1>Application models</h1>
<p>Download models for your analyses here. Each file is verified before saving.
Existing models are preserved, and modified files are never automatically replaced.
MyoSurface does not require an external model.</p>
<div id="catalog" aria-live="polite">Loading models…</div>
<p>Verified models are suggested in application file selectors when you next open them.
You can still choose your own model file in each application.</p>
</main><script>
const token=""" + json.dumps(MODEL_TOKEN) + """;
const root=document.getElementById('catalog');
async function refresh(){
 const r=await fetch('/api/models',{cache:'no-store'});
 if(!r.ok)throw Error('Unable to load models.');
 const items=await r.json();root.replaceChildren();
 for(const item of items){
  const card=document.createElement('section');card.className='model';
  const title=document.createElement('h2');title.textContent=item.name;card.append(title);
  if(item.version){const v=document.createElement('p');v.className='feedback';v.textContent='Model version: v'+item.version;card.append(v);}
  const use=document.createElement('p');use.textContent=item.applications;card.append(use);
  const location=document.createElement('p');const code=document.createElement('code');
  code.textContent=item.path;location.append('Path: ',code);card.append(location);
  const link=document.createElement('a');link.href=item.release;link.target='_blank';
  link.rel='noopener noreferrer';link.textContent='View model source';card.append(link);
  const line=document.createElement('p');line.className='feedback';
  line.textContent=item.installed?'Installed and verified':'Not installed';card.append(line);
  const button=document.createElement('button');button.className='open';button.type='button';
  button.textContent=item.installed?'Already available':'Download and verify';button.disabled=item.installed;
  button.addEventListener('click',async()=>{
   button.disabled=true;line.textContent='Downloading…';
   try{
    const response=await fetch('/api/models/'+item.id,{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});
    const result=await response.json();
    if(!response.ok)throw Error(result.error||'Download failed');
    line.textContent='Installed and verified: '+result.path;
    button.textContent='Already available';
   }catch(error){line.textContent=String(error);button.disabled=false;}
  });card.append(button);root.append(card);
 }
}
refresh().catch(error=>{root.textContent=String(error);});
</script></body></html>"""


def uninstallpage():
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Uninstall MyoTools</title><style>""" + STYLE + """
.uninstall{display:block;max-width:850px;padding:28px}.uninstall label{display:block;margin:20px 0 8px}
.uninstall input{padding:12px;width:min(100%,400px);font:inherit}.uninstall button{margin:15px 0;border:0;cursor:pointer}
.uninstall button:disabled{opacity:.45;cursor:default}.uninstall pre{white-space:pre-wrap;overflow-wrap:anywhere}
</style></head><body><main class="uninstall"><a href="/">← Back to MyoTools</a>
<h1>Uninstall MyoTools</h1>
<p>Only environments created and identified by this installation can be removed:
<b>myotools</b> and <b>myofuse_env</b>, plus the desktop shortcut pointing here.</p>
<p>Anaconda/Miniforge, notebooks, models and scientific data are kept.
Pre-existing environments and environments without matching ownership records are retained.</p>
<p>Save your work and close analysis and review windows before continuing.
The notebook servers started by this hub will be stopped.</p>
<div id="plan" aria-live="polite">Checking this installation…</div>
<form id="uninstall-form"><label for="confirmation">Type <b>UNINSTALL MYOTOOLS</b> to confirm:</label>
<input id="confirmation" autocomplete="off" spellcheck="false" required>
<br><button class="open" id="remove" type="submit" disabled>Uninstall MyoTools</button></form>
<pre id="result" role="status" aria-live="polite"></pre>
</main><script>
const token=""" + json.dumps(UNINSTALL_TOKEN) + """;
const expected=""" + json.dumps(CONFIRMATION) + """;
const field=document.getElementById('confirmation'), button=document.getElementById('remove');
let ready=false, busy=false;
field.addEventListener('input',()=>{button.disabled=!ready||busy||field.value!==expected;});
fetch('/api/uninstall/plan',{cache:'no-store'}).then(async r=>{
 if(!r.ok)throw Error('Unable to check this installation');
 const p=await r.json(), box=document.getElementById('plan');box.textContent='';
 for(const e of p.environments){const line=document.createElement('p');
  line.textContent=e.name+': '+(e.state==='owned'?'Will remove '+e.prefix:'Retained — '+e.message);box.append(line);}
 const line=document.createElement('p');line.textContent='Desktop shortcut: '+p.shortcut.message;box.append(line);
 ready=true;button.disabled=field.value!==expected;
}).catch(e=>{document.getElementById('plan').textContent=String(e);});
document.getElementById('uninstall-form').addEventListener('submit',async event=>{
 event.preventDefault();if(!ready||busy||field.value!==expected)return;
 busy=true;button.disabled=true;field.disabled=true;
 const output=document.getElementById('result');output.textContent='Uninstalling… Please keep this window open.';
 try{
  const r=await fetch('/api/uninstall',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({token,confirmation:field.value})});
  const result=await r.json();if(!r.ok)throw Error(result.error||'Uninstallation failed');
  const lines=result.environments.map(e=>e.name+': '+e.state+' — '+(e.prefix||e.message||''));
  lines.push('Desktop shortcut: '+result.shortcut.message);
  lines.push(...result.errors);
  lines.push('Finished. Retained items were kept. You can close MyoTools now.');
  output.textContent=lines.join('\\n');
 }catch(e){output.textContent=String(e)+' — Check the terminal. Close and restart the uninstaller to inspect remaining items.';}
});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def local_request(self):
        expected = "127.0.0.1:%d" % self.server.server_port
        return (self.headers.get("Host") == expected and
                self.headers.get("Origin", "http://" + expected) == "http://" + expected)

    def reply(self,code,data,kind):
        raw=data.encode("utf-8")
        self.send_response(code);self.send_header("Content-Type",kind)
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        path=self.path.split("?",1)[0]
        if path in ("/updates", "/api/updates/status"):
            if not self.local_request():
                return self.reply(403,"Local origin required","text/plain")
            if path == "/updates":
                return self.reply(200,update_page.page(STYLE,UPDATE_TOKEN),"text/html; charset=utf-8")
            try:
                return self.reply(200,json.dumps(update_service.inspect(ROOT)),"application/json")
            except (OSError,ValueError,KeyError,updater.UpdateError) as exc:
                return self.reply(503,json.dumps({"error":str(exc)}),"application/json")
        if path in ("/models", "/api/models"):
            if not self.local_request():
                return self.reply(403,"Local origin required","text/plain")
            if path == "/models":
                return self.reply(200,modelspage(),"text/html; charset=utf-8")
            return self.reply(200,json.dumps(model_manager.catalog()),"application/json")
        if path in ("/uninstall", "/api/uninstall/plan"):
            if not self.local_request():
                return self.reply(403,"Local origin required","text/plain")
            if path == "/uninstall":
                return self.reply(200,uninstallpage(),"text/html; charset=utf-8")
            return self.reply(200,json.dumps(uninstaller.plan()),"application/json")
        if path == "/assets/microscopy-sprite.webp":
            image_data = ROOT / "Hub" / "assets" / "microscopy-sprite.webp"
            if not image_data.is_file():
                self.send_error(404, "Microscopy asset unavailable")
                return
            raw = image_data.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/webp")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path=="/":return self.reply(200,homepage(),"text/html; charset=utf-8")
        if path=="/api/status":return self.reply(200,json.dumps({x.id:status(x) for x in TOOLS}),"application/json")
        if path.startswith("/launch/") and path.split("/")[-1] in APPS:
            return self.reply(200,launchpage(path.split("/")[-1]),"text/html; charset=utf-8")
        return self.reply(404,"Not found","text/plain")
    def do_POST(self):
        global UNINSTALLING, UPDATE_SHUTDOWN
        path=self.path.split("?",1)[0]
        if path in ("/api/updates/check", "/api/updates/download",
                    "/api/updates/install", "/api/updates/rollback"):
            if not self.local_request() or self.headers.get("Content-Type") != "application/json":
                return self.reply(403,json.dumps({"error":"Local JSON request required"}),"application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2048:
                    raise ValueError("Invalid request length")
                payload = json.loads(self.rfile.read(length))
                if (not isinstance(payload,dict) or not isinstance(payload.get("token"),str) or
                    not secrets.compare_digest(payload["token"],UPDATE_TOKEN)):
                    raise ValueError("Valid session token required")
            except (ValueError,TypeError) as exc:
                return self.reply(400,json.dumps({"error":str(exc)}),"application/json")
            if not UPDATE_LOCK.acquire(blocking=False):
                return self.reply(409,json.dumps({"error":"Another update operation is active"}),"application/json")
            try:
                with LOCK:
                    if UNINSTALLING:
                        return self.reply(409,json.dumps({"error":"Uninstallation has started"}),"application/json")
                if path.endswith("/check"):
                    result=updater.check(ROOT)
                elif path.endswith("/download"):
                    result=updater.download(ROOT)
                else:
                    if payload.get("confirmation") != updater.CONFIRMATION:
                        return self.reply(400,json.dumps({"error":"Type UPDATE MYOTOOLS to confirm"}),"application/json")
                    with LOCK:
                        if UPDATE_SHUTDOWN:
                            return self.reply(409,json.dumps({"error":"Hub maintenance is already starting"}),"application/json")
                        active = [rec["process"].pid for rec in RUNNING.values()
                                  if rec["process"].poll() is None]
                        if active:
                            return self.reply(409,json.dumps({"error":"Close running applications and save your work before updating"}),"application/json")
                        result = update_service.queue(ROOT,
                            "install" if path.endswith("/install") else "rollback",
                            os.getpid(),sys.executable,active)
                        UPDATE_SHUTDOWN = True
                    # The HTTP reply must finish before the detached worker may
                    # replace any of the source files currently executing.
                    def close_for_update():
                        time.sleep(0.7)
                        stop()
                        self.server.shutdown()
                    threading.Thread(target=close_for_update,daemon=True).start()
                return self.reply(200,json.dumps(result),"application/json")
            except (OSError,ValueError,KeyError,updater.UpdateError) as exc:
                return self.reply(503,json.dumps({"error":str(exc)}),"application/json")
            finally:
                UPDATE_LOCK.release()
        if path.startswith("/api/models/"):
            if not self.local_request() or self.headers.get("Content-Type") != "application/json":
                return self.reply(403,json.dumps({"error":"Local JSON request required"}),"application/json")
            key = path.rsplit("/",1)[-1]
            if key not in (*model_manager.MODELS, "svetlana"):
                return self.reply(404,json.dumps({"error":"Unknown model"}),"application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2048:
                    raise ValueError("Invalid request length")
                payload = json.loads(self.rfile.read(length))
                if (not isinstance(payload,dict) or not isinstance(payload.get("token"),str) or
                        not secrets.compare_digest(payload["token"],MODEL_TOKEN)):
                    raise ValueError("Valid session token required")
            except (ValueError, TypeError) as exc:
                return self.reply(400,json.dumps({"error":str(exc)}),"application/json")
            if UNINSTALLING:
                return self.reply(409,json.dumps({"error":"Uninstallation has started"}),"application/json")
            if not MODEL_LOCK.acquire(blocking=False):
                return self.reply(409,json.dumps({"error":"Another model is downloading"}),"application/json")
            try:
                target = model_manager.install(key)
                return self.reply(200,json.dumps({"path":str(target)}),"application/json")
            except Exception as exc:
                return self.reply(503,json.dumps({"error":str(exc)}),"application/json")
            finally:
                MODEL_LOCK.release()
        if path == "/api/uninstall":
            if not self.local_request() or self.headers.get("Content-Type") != "application/json":
                return self.reply(403,json.dumps({"error":"Local JSON request required"}),"application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2048:
                    raise ValueError("Invalid request length")
                payload = json.loads(self.rfile.read(length))
                if (not isinstance(payload, dict) or not isinstance(payload.get("token"), str) or
                        not secrets.compare_digest(payload["token"], UNINSTALL_TOKEN) or
                        payload.get("confirmation") != CONFIRMATION):
                    raise ValueError("Explicit confirmation and valid session token required")
            except (ValueError, TypeError) as exc:
                return self.reply(400,json.dumps({"error":str(exc)}),"application/json")
            with LOCK:
                if UNINSTALLING:
                    return self.reply(409,json.dumps({"error":"Uninstallation already started"}),"application/json")
                if not UPDATE_LOCK.acquire(blocking=False):
                    return self.reply(409,json.dumps({"error":"Wait for the update operation to finish"}),"application/json")
                UNINSTALLING = True
                try:
                    stop()
                    result = uninstaller.uninstall(payload["confirmation"])
                    return self.reply(200,json.dumps(result),"application/json")
                except Exception as exc:
                    return self.reply(503,json.dumps({"error":str(exc)}),"application/json")
                finally:
                    UPDATE_LOCK.release()
        if UPDATE_SHUTDOWN:
            return self.reply(409,json.dumps({"error":"Hub is shutting down for an update"}),"application/json")
        if not path.startswith("/api/start/") or path.split("/")[-1] not in APPS:
            return self.reply(404,json.dumps({"error":"Unknown application"}),"application/json")
        try:return self.reply(200,json.dumps(start(APPS[path.split("/")[-1]])),"application/json")
        except Exception as exc:return self.reply(503,json.dumps({"error":str(exc)}),"application/json")
    def log_message(self,*args):pass

if __name__=="__main__":
    if "--check" in sys.argv:
        print("Hub mode:",MODE)
        print("Conda:",conda_command() or "NOT FOUND")
        for item in TOOLS:print(item.name+": "+status(item)["message"])
        sys.exit(0)
    # Advertise the actual Hub PID so maintenance can refuse active installations.
    runtime = ROOT / "Hub" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    pid_marker = runtime / ("hub-%d.pid" % os.getpid())
    pid_marker.write_text(str(os.getpid()), encoding="utf-8")
    try:
        with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
            url="http://127.0.0.1:%d/" % server.server_port
            print("MyoTools Hub: "+url+"\nClose this window to stop.",flush=True)
            if "--no-browser" not in sys.argv:webbrowser.open(url)
            try:server.serve_forever(poll_interval=0.35)
            except KeyboardInterrupt:pass
            finally:stop()
    finally:
        pid_marker.unlink(missing_ok=True)

