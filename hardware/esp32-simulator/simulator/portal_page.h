#pragma once
#include <Arduino.h>

static const char CONFIG_FORM[] PROGMEM = R"PORTAL(
<h2>Connection mode</h2>
<form method="post" action="/configure">
<input type="hidden" name="token" value="{{TOKEN}}">
<label class="choice"><input type="radio" name="mode" value="hotspot" {{HOTSPOT}}>Keep a local hotspot for the phone</label>
<label class="choice"><input type="radio" name="mode" value="station" {{STATION}}>Join another Wi-Fi network</label>
<p id="modeHint"></p>
<section id="stationFields">
<button id="scanButton" type="button">Scan nearby Wi-Fi networks</button>
<p id="scanStatus" role="status" aria-live="polite">Select Scan to find 2.4 GHz networks.</p>
<label>Available networks<select id="networks"><option value="">Select a network after scanning</option></select></label>
<label>Network name / SSID<input id="ssid" name="ssid" maxlength="32" autocomplete="off" value="{{SSID}}"></label>
<p id="security">Security is negotiated automatically for supported networks.</p>
<label>Password<input id="password" type="password" name="password" maxlength="64" autocomplete="new-password"></label>
<small>Open, WPA and WPA2 Personal supported. Unsupported security is marked in scan results.
For a hidden network, enter its SSID manually.</small>
</section>
<button id="saveButton">Save mode and reboot</button>
</form>
<script>
const $=id=>document.getElementById(id);
const mode=()=>document.querySelector('input[name=mode]:checked').value;
let scanRunning=false;
function updateMode(){
 const local=mode()==='hotspot';
 $('stationFields').hidden=local;
 $('ssid').required=!local;
 $('ssid').disabled=local;
 $('password').disabled=local;
 $('scanButton').disabled=local||scanRunning;
 $('modeHint').textContent=local?
  'After reboot, join {{APNAME}} (password: cosmossetup). Setup page: http://1.2.3.4 and telescope port: 2000. No router needed.':
  'Select your router network and enter its password. The simulator saves it, reboots and reconnects automatically.';
}
document.querySelectorAll('input[name=mode]').forEach(r=>r.addEventListener('change',updateMode));
$('ssid').addEventListener('input',()=>{
 $('password').disabled=false;
 $('security').textContent='Security is negotiated automatically for supported networks.';
});
$('networks').addEventListener('change',()=>{
 const selected=$('networks').selectedOptions[0];
 if(!selected||!selected.value)return;
 $('ssid').value=selected.value;
 $('security').textContent='Detected security: '+selected.dataset.security;
 $('password').disabled=selected.dataset.open==='1';
 if($('password').disabled)$('password').value='';
 else $('password').focus();
});
async function fetchScan(url){
 const controller=new AbortController();
 const timer=setTimeout(()=>controller.abort(),6000);
 try{return await fetch(url,{cache:'no-store',signal:controller.signal});}
 finally{clearTimeout(timer);}
}
$('scanButton').addEventListener('click',async()=>{
 if(scanRunning)return;
 scanRunning=true;updateMode();
 $('scanStatus').className='scanning';
 $('scanStatus').textContent='Scanning nearby Wi-Fi…';
 const started=Date.now();
 try{
  let response=await fetchScan('/scan?start=1');
  while(response.status===202){
   if(Date.now()-started>25000)throw new Error('Scan timed out. Try again.');
   await new Promise(resolve=>setTimeout(resolve,700));
   response=await fetchScan('/scan');
  }
  if(!response.ok)throw new Error(await response.text());
  const data=await response.json();
  const select=$('networks');select.replaceChildren();
  const placeholder=document.createElement('option');placeholder.value='';
  placeholder.textContent='Select your Wi-Fi network';select.appendChild(placeholder);
  data.networks.sort((a,b)=>b.rssi-a.rssi);
  for(const network of data.networks){
   const option=document.createElement('option');
   option.value=network.ssid;
   option.textContent=(network.ssid||'[hidden network]')+' — '+network.rssi+' dBm — '+network.security;
   option.disabled=!network.supported||!network.ssid;
   option.dataset.security=network.security;option.dataset.open=network.open?'1':'0';
   select.appendChild(option);
  }
  $('scanStatus').textContent=data.networks.length+' networks found. Choose one below.';
 }catch(error){$('scanStatus').textContent='Scan failed: '+error.message;}
 finally{scanRunning=false;$('scanStatus').className='';updateMode();}
});
updateMode();
</script>
)PORTAL";
