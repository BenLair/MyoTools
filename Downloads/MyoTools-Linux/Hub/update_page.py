"""MyoTools Hub update page: verified downloads and explicit maintenance handoff."""
from __future__ import annotations

import json


def page(style: str, session_token: str) -> str:
    """Render the update UI using only locally generated, trusted template values."""
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Software updates | MyoTools</title><style>""" + style + """
.updates{display:block;max-width:900px;padding:28px}
.updates h1{margin:28px 0 9px}
.updates p{line-height:1.55;color:#544c72}
.updates .panel{background:#fff;border:1px solid #e7dff7;border-radius:16px;padding:22px;margin:18px 0}
.updates .panel h2{font-size:19px;margin:0 0 10px}
.updates .panel p{margin:7px 0}
.updates button{border:0;cursor:pointer;margin:10px 10px 10px 0;font-family:inherit}
.updates button:disabled{opacity:.45;cursor:not-allowed}
.updates code{overflow-wrap:anywhere}
.updates .feedback{white-space:pre-wrap;overflow-wrap:anywhere;color:#4e348c}
.updates .secondary-action{color:#60429c;background:#eee8fa;border-radius:10px;padding:12px 19px;font-size:15px}
</style></head><body><main class="updates">
<a href="/">← Back to MyoTools</a>
<h1>Software updates</h1>
<p>Check for newer MyoTools versions from the branch configured for this installation.
The updater accepts packages only from the repository and branch fixed in this installation.
Trained model weights are managed separately on the Models page.</p>
<section class="panel" aria-label="Current installation">
<h2>Current installation</h2>
<p>Version: <b id="installed">Loading…</b></p>
<p>Update channel: <b id="channel">Loading…</b></p>
<p>Platform: <b id="platform">Loading…</b></p>
</section>
<section class="panel" aria-label="Update check and download">
<h2>Check and download</h2>
<p>Update downloads are verified against SHA-256 checksums and the distribution
manifest from one pinned GitHub commit. Verified ZIPs are kept under
<code>Hub/runtime/updates/downloads/</code>.</p>
<button class="open" type="button" id="check-update">Check for updates</button>
<button class="secondary-action" type="button" id="download-update" disabled>Download and verify</button>
<p id="update-result" class="feedback" role="status" aria-live="polite">No update check has been run yet.</p>
</section>
<section class="panel" aria-label="Installation and rollback">
<h2>Install and rollback</h2>
<p>After downloading, save your work and <b>close all open applications</b>.
Installation and rollback use a separate maintenance process, stop this Hub,
replace only managed files, and reopen the updated Hub.</p>
<label for="confirm-update">Type <b>UPDATE MYOTOOLS</b> to confirm:</label>
<input id="confirm-update" type="text" autocomplete="off" spellcheck="false" placeholder="UPDATE MYOTOOLS"
 style="display:block;padding:11px;width:min(100%,340px);margin:12px 0;border:1px solid #c8b9e4;border-radius:9px">
<button class="secondary-action" type="button" id="install-update" disabled>Install downloaded update and restart</button>
<button class="secondary-action" type="button" id="rollback-update" disabled>Rollback previous update and restart</button>
<p id="maintenance-status" class="feedback" role="status" aria-live="polite">No maintenance operation is running.</p>
<p>Conda environments, trained models and scientific results are preserved.</p>
</section></main><script>
const updateToken=""" + json.dumps(session_token) + """;
const checkButton=document.getElementById('check-update');
const downloadButton=document.getElementById('download-update');
const resultLine=document.getElementById('update-result');
let waiting=false;
let downloadAvailable=false;
let installedUpdateAvailable=false;
let rollbackAllowed=false;
const installButton=document.getElementById('install-update');
const rollbackButton=document.getElementById('rollback-update');
const confirmField=document.getElementById('confirm-update');
const maintenanceStatus=document.getElementById('maintenance-status');
function updateMaintenanceButtons(){
 const confirmed=confirmField.value==='UPDATE MYOTOOLS';
 installButton.disabled=waiting||!confirmed||!installedUpdateAvailable;
 rollbackButton.disabled=waiting||!confirmed||!rollbackAllowed;
}
confirmField.addEventListener('input',updateMaintenanceButtons);

function setBusy(value){
 waiting=value;
 checkButton.disabled=value;
 downloadButton.disabled=value||!downloadAvailable;
 updateMaintenanceButtons();
}
function showResult(info){
 const state=String(info.status||'');
 if(state==='available'){
  resultLine.textContent='Version '+info.latest+' is available on '+info.channel+
   '. Ready to download and verify.';
  downloadAvailable=true;
  installedUpdateAvailable=false;
 }else if(state==='up-to-date'){
  resultLine.textContent='MyoTools '+info.installed+' is up to date on '+info.channel+'.';
  downloadAvailable=false;
  installedUpdateAvailable=false;
 }else if(state==='downloaded'){
  resultLine.textContent='Verified archive saved at:\\n'+info.path+
    '\\nSHA-256: '+info.sha256+
    '\\nThis update is ready to install after closing running applications.';
  downloadAvailable=false;
  installedUpdateAvailable=true;
 }else{
  resultLine.textContent=info.message||('Update status: '+state);
  downloadAvailable=false;
  installedUpdateAvailable=false;
 }
 updateMaintenanceButtons();
}
async function perform(action){
 if(waiting)return;
 setBusy(true);
 resultLine.textContent=action==='check'?'Checking the selected GitHub branch…':
  'Downloading and verifying the archive… This can take a while.';
 try{
  const response=await fetch('/api/updates/'+action,{
   method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({token:updateToken})
  });
  const data=await response.json();
  if(!response.ok)throw Error(data.error||'Update request failed');
  showResult(data);
 }catch(error){
  resultLine.textContent='Update error: '+String(error);
  downloadAvailable=false;
 }finally{setBusy(false);}
}
checkButton.addEventListener('click',()=>perform('check'));
downloadButton.addEventListener('click',()=>perform('download'));
async function inspectLocal(){
 const response=await fetch('/api/updates/status',{cache:'no-store'});
 if(!response.ok)throw Error('Cannot inspect this MyoTools installation');
 const info=await response.json();
 document.getElementById('installed').textContent=info.installed;
 document.getElementById('channel').textContent=info.channel;
 document.getElementById('platform').textContent=info.platform;
 rollbackAllowed=Boolean(info.rollback_enabled);
 if(info.operation){
  maintenanceStatus.textContent=(info.operation.status||'')+': '+(info.operation.details||'');
 }
 updateMaintenanceButtons();
}
async function maintenance(action){
 if(waiting||confirmField.value!=='UPDATE MYOTOOLS')return;
 if(!window.confirm('Close MyoTools and '+(action==='install'?'install the update':'roll back')+
   '? Save your work and close all analysis windows first.'))return;
 setBusy(true);
 maintenanceStatus.textContent='Preparing secure maintenance handoff…';
 try{
  const response=await fetch('/api/updates/'+action,{method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({token:updateToken,confirmation:confirmField.value})});
  const result=await response.json();
  if(!response.ok)throw Error(result.error||'Maintenance handoff failed');
  maintenanceStatus.textContent=result.message||
   'MyoTools is closing. Wait for the updated Hub to reopen.';
  // Hub will terminate. Do not retry a queued action from this page.
  installButton.disabled=true;
  rollbackButton.disabled=true;
  checkButton.disabled=true;
  downloadButton.disabled=true;
 }catch(error){
  maintenanceStatus.textContent='Maintenance error: '+String(error);
  setBusy(false);
  inspectLocal().catch(()=>{});
 }
}
installButton.addEventListener('click',()=>maintenance('install'));
rollbackButton.addEventListener('click',()=>maintenance('rollback'));
inspectLocal().catch(error=>{resultLine.textContent='Installation details unavailable: '+String(error);});
</script></body></html>"""
