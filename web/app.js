'use strict';
const screen=document.querySelector('#screen'), feedback=document.querySelector('#feedback');
let page='home', state=null, draft=null, preferences=null, navigation=0, pollBusy=false, cameraBusy=false, feedbackTimer, modalRefresh=null, modalCleanup=null;
const $=id=>screen.querySelector(`[data-node-id="${id}"]`);
const text=(id,value)=>{const e=$(id);if(e)e.textContent=value;};
const duration=n=>{n=Math.max(0,Math.floor(n||0));return [Math.floor(n/3600),Math.floor(n/60)%60,n%60].map(x=>String(x).padStart(2,'0')).join(':');};
function notify(message){feedback.textContent=message;feedback.hidden=false;clearTimeout(feedbackTimer);feedbackTimer=setTimeout(()=>feedback.hidden=true,6000);}
async function api(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;}
async function action(name,data={}){try{await api('api/action',{action:name,data});if(name!=='shutdown'){state=await api('api/state');renderState();}return true;}catch(e){notify(e.message);return false;}}
function resize(){const scale=Math.min(innerWidth/1440,innerHeight/900);screen.style.transform=`scale(${scale})`;document.querySelector('#viewport').style.cssText=`width:${1440*scale}px;height:${900*scale}px`;}
addEventListener('resize',resize);
function hit(label,x,y,w,h,fn){const b=document.createElement('button');b.className='hit';b.style.cssText=`left:${x}px;top:${y}px;width:${w}px;height:${h}px`;b.setAttribute('aria-label',label);b.onclick=fn;screen.append(b);return b;}
function cleanupModal(){modalRefresh=null;if(modalCleanup){const clean=modalCleanup;modalCleanup=null;clean();}}
function modal(title,build){cleanupModal();const d=document.querySelector('#details'),c=document.querySelector('#details-content');c.replaceChildren();const h=document.createElement('h2');h.textContent=title;c.append(h);build(c);if(!d.open)d.showModal();}
document.querySelector('#close-details').onclick=()=>{document.querySelector('#details').close();modalRefresh=null;};
document.querySelector('#details').addEventListener('close',cleanupModal);
function button(label,fn,parent){const b=document.createElement('button');b.className='action';b.textContent=label;b.onclick=fn;parent.append(b);return b;}
async function navigate(next){const seq=++navigation;const markup=await (await fetch(next+'.html')).text();if(seq!==navigation)return;
 if(page==='calibration'&&next!=='calibration')await action('close_preview');
 page=next;screen.innerHTML=markup;resize();
 // Layout and static assets come from the matching Figma frame.
 if(page!=='calibration'){
  hit('Home',35,315,102,90,()=>navigate('home'));hit('History',35,420,102,90,()=>navigate('history'));hit('Settings',35,522,102,90,()=>navigate('general'));
  const logo=[...screen.querySelectorAll('p')].find(e=>e.textContent.trim()==='E.');if(logo)logo.hidden=true;const brand=document.createElement('div');brand.className='sora-brand';const mark=document.createElement('img');mark.src='assets/sora-logo.png';mark.alt='Sora logo';const word=document.createElement('span');word.textContent='SORA';brand.append(mark,word);screen.append(brand);
 }
 const settingPages=['general','intervals','notifications','camera','privacy','about'];
 if(settingPages.includes(page)){
  ['General','Time Intervals','Notifications & Display','Camera & Calibration','Privacy','About'].forEach((label,i)=>hit(label,198,[268,317,366,415,540,589][i],268,42,()=>navigate(settingPages[i])));
  if(!draft){draft=structuredClone(state.config);preferences=structuredClone(state.preferences);}
  if(!['privacy','about'].includes(page))hit('Save changes',542,772,813,56,async()=>{if(await action('save_settings',{config:draft,preferences})){draft=structuredClone(state.config);notify('Settings saved. These settings apply to the next session.');}});
 }
 if(page==='home'){
  screen.startButton=hit('Start session',877,214,410,102,async()=>{if(await action('start')){if(!state.calibrated)navigate('calibration');}});
  screen.pauseButton=hit('Pause or resume session',878,343,185,75,()=>action(state.phase==='paused'?'resume':'pause'));
  screen.endButton=hit('End session',1102,343,185,75,()=>action('end'));
  text('53:197','Present condition');for(const p of screen.querySelectorAll('p')){if(p.textContent.trim()==='Fatigue detection')p.textContent='Fatigue cues';if(p.textContent.trim()==='Screen distance')p.textContent='Relative distance';}text('53:340','Time near reference');text('53:367','Near-reference streak');text('53:338','Of usable observations');text('53:371','Based on observed head position, not a health score.');text('53:370','Longest continuous time near your reference.');
  $('53:338').style.fontSize='12px';$('53:338').style.left='785px';
  ['53:210','53:213'].forEach(id=>{text(id,'Not available');$(id).style.fontSize='11px';$(id).style.left='503px';});
  ['53:209','53:212'].forEach(id=>{$(id).style.background='#666';$(id).style.left='499px';$(id).style.width='80px';});
  text('53:199','Screen distance');
 }
 if(page==='general')setupGeneral();
 if(page==='intervals')setupIntervals();
 if(page==='notifications')setupNotifications();
 if(page==='camera'){
  hit('Recalibration',542,677,813,54,()=>navigate('calibration'));addCamera(542,319,815,294);
 }
 if(page==='privacy'){
  const ul=screen.querySelector('ul');if(ul){ul.replaceChildren();['Camera frames are processed on this device. They are not saved or uploaded.','Local session summaries contain timestamps, durations, posture observations and reminder actions.','AWS is optional and off by default. When configured, only derived decision flags go to your AWS account; no frames or audio.', 'Optional meeting suppression reads Windows microphone-use metadata and running app names. It can mistake other microphone use for a meeting.','Start or Calibrate activates the camera. Pause, End and Quit release it.','Visual estimates include likely drinking motions, relative camera distance and prolonged eye closure. They are not medical measurements.'].forEach(t=>{const li=document.createElement('li');li.textContent=t;li.style.cssText='margin-left:33px;line-height:1.45';ul.append(li);});}
 }
 if(page==='about'){
  $('123:1691').innerHTML='<li style="margin-left:33px;line-height:normal">Application: Sora — AI Work Companion</li><li style="margin-left:33px;line-height:normal">Version: 1.7.1 — Logo and camera preview</li>';
  $('123:1692').textContent='Sora combines local OpenCV posture observations with configurable water, movement, screen-break and session-limit reminders. The interface comes from the team’s Uxse Figma design. Local face landmarks support relative distance and prolonged eye-closure cues. Vessel motion estimates likely sips, with manual correction. This prototype does not diagnose health conditions, measure fluid volume, or verify sleep.';$('123:1692').style.lineHeight='1.5';
 }
 if(page==='calibration'){
  addCamera(73,258,1294,460);const bar=document.createElement('div');bar.className='progress';bar.id='cal-progress';screen.append(bar);const message=document.createElement('div');message.className='cal-status';message.id='cal-status';screen.append(message);
  hit('Back',73,789,117,54,()=>navigate('home'));screen.calButton=hit('Start calibration',1104,788,263,54,()=>action('calibrate'));
 }
 if(page==='history'){await updateHistory();hit('See all activity',1280,644,112,45,showHistory);}
 const footer=document.createElement('div');footer.className='footer';
 if(page==='home'){button('Open camera',showCamera,footer);button('Timers & actions',showTimers,footer);button('Calibrate',()=>navigate('calibration'),footer);button('Agent activity',showAgent,footer);}
 button('Quit Sora',()=>modal('Quit Sora?',c=>{const p=document.createElement('p');p.textContent='The camera will stop and your session summary will be saved.';c.append(p);button('Quit',async()=>{await action('shutdown');document.querySelector('#details').close();notify('Sora stopped. You can close this tab.');},c);}),footer);
 const mode=document.createElement('span');mode.className='mode';mode.id='mode';footer.append(mode);screen.append(footer);renderState();
}
function setupSwitch(el,key,enabled){el.setAttribute('role','switch');el.setAttribute('aria-label',key);el.setAttribute('aria-checked',String(enabled));const knob=el.querySelector('[data-node-id="34:344"]');if(knob){knob.style.left=enabled?'55.71%':'5.71%';knob.style.right=enabled?'5.71%':'55.71%';knob.style.background=enabled?'#426100':'#3423a6';}}
function setupGeneral(){
 const switches=[...screen.querySelectorAll('button[data-node-id="34:363"]')],keys=['water','posture','distance','fatigue','sleep','eyes',null,'automatic_meeting'];
 switches.forEach((el,i)=>{const key=keys[i];if(i===6){setupSwitch(el,'Start with Windows',preferences.autostart);el.onclick=()=>{preferences.autostart=!preferences.autostart;setupSwitch(el,'Start with Windows',preferences.autostart);};return;}if(!key){el.disabled=true;el.classList.add('unavailable');el.setAttribute('aria-label','Not available in this build');return;}setupSwitch(el,key+' reminder',draft[key].enabled);el.onclick=()=>{draft[key].enabled=!draft[key].enabled;setupSwitch(el,key+' reminder',draft[key].enabled);};});
 text('107:453','Water timer with automatic likely-sip estimates.');text('107:465','Relative to your calibrated camera position.');text('107:469','Eye-closure and possible-yawn cues after warm-up.');text('105:1155','Open Sora on sign-in. Camera stays off until Start.');text('105:1159','Possible meeting from microphone use; no audio recorded.');text('107:477','Offer a break after the configured observed time.');text('107:472','Session-limit reminder');
 for(const [i,key,title,desc] of [[0,'movement','Movement reminder','Suggest standing or stretching after observed time.'],[1,'dark_camera','Low-light reminder','Notify when the camera view becomes too dark.'],[2,'automatic_drinking','Automatic drinking','Estimate likely sips; review or undo in Timers & actions.'],[3,'straw_assist','Experimental straw assist','Use straight-line cues near the mouth; may be inaccurate.']]){
  const row=document.createElement('div');row.className='setting-extra';row.style.top=(800+i*90)+'px';row.innerHTML='<div class="heading"></div><div class="description"></div>';row.children[0].textContent=title;row.children[1].textContent=desc;const s=document.createElement('button');s.className='switch';setupSwitch(s,title,draft[key].enabled);s.onclick=()=>{draft[key].enabled=!draft[key].enabled;setupSwitch(s,title,draft[key].enabled);};row.append(s);$('107:495').append(row);
 }
}
function setupIntervals(){
 text('123:1076','Reminder intervals');text('123:1149','Reminder intervals');
 const configs=[['water','interval_seconds',605,369],['posture','window_seconds',603,491],['eyes','interval_seconds',605,613]];
 [...screen.querySelectorAll('button')].filter(e=>e.style.width==='690px').forEach(e=>{e.disabled=true;e.querySelectorAll('p').forEach(p=>p.hidden=true);});
 configs.forEach(([key,field,x,y])=>{const sel=document.createElement('select');sel.className='field-select';sel.style.cssText=`left:${x}px;top:${y}px;width:620px;height:54px`;sel.setAttribute('aria-label',key+' interval');const values=[...new Set([draft[key][field],60,300,600,1200,1800,3600,7200])].sort((a,b)=>a-b);values.forEach(v=>sel.add(new Option(v>=60?`${v/60} Minutes`:`${v} Seconds`,v)));sel.value=draft[key][field];sel.onchange=()=>draft[key][field]=Number(sel.value);screen.append(sel);});
 text('123:1084','Screen-break reminder');
 const b=hit('More timer settings',605,685,690,45,()=>modal('Additional timer settings',c=>{for(const [label,key,field] of [['Movement interval (minutes)','movement','interval_seconds'],['Session limit (minutes)','sleep','interval_seconds'],['Break duration (minutes)','break_seconds',null],['Snooze (minutes)','snooze_seconds',null]]){const row=document.createElement('label');row.className='row';row.textContent=label;const input=document.createElement('input');input.type='number';input.min='.05';input.step='any';input.value=(field?draft[key][field]:draft[key])/60;input.onchange=()=>{const v=Number(input.value)*60;if(!Number.isFinite(v)||v<=0){notify('Enter a positive duration.');return;}if(field)draft[key][field]=v;else draft[key]=v;};row.append(input);c.append(row);}button('Done',()=>document.querySelector('#details').close(),c);}));b.textContent='More timer settings';b.style.color='#111';b.style.fontSize='20px';
}
function setupNotifications(){
 const toggles=[...screen.querySelectorAll('button[data-node-id="34:363"]')];setupSwitch(toggles[0],'Animated reminders',preferences.animation);toggles[0].onclick=()=>{preferences.animation=!preferences.animation;setupSwitch(toggles[0],'Animated reminders',preferences.animation);};
 setupSwitch(toggles[1],'Reminder alert sound',preferences.sound);toggles[1].onclick=()=>{preferences.sound=!preferences.sound;setupSwitch(toggles[1],'Reminder alert sound',preferences.sound);};
 text('123:1307','Transparent character reminders; turn off for a still character.');
 const preview=hit('Preview animations',550,746,385,24,()=>modal('Preview reminders',c=>{for(const [kind,label] of [['water','Water'],['posture','Posture'],['distance','Distance'],['fatigue','Eye closure'],['eyes','Break'],['sleep','Session limit']])button(label,()=>action('preview_notice',{kind}),c);}));preview.textContent='Preview animations';preview.style.color='#111';
 for(const [position,x] of [['center',546],['edge',969]]){const b=hit('Popup position '+position,x,503,388,240,()=>{preferences.position=position;highlight();});b.dataset.position=position;}
 function highlight(){screen.querySelectorAll('[data-position]').forEach(b=>b.style.outline=b.dataset.position===preferences.position?'4px solid #b2ff00':'none');}highlight();
}
function addCamera(x,y,w,h){const img=document.createElement('img');img.className='cam-live';img.alt='Live camera preview';img.hidden=true;img.style.cssText=`left:${x}px;top:${y}px;width:${w}px;height:${h}px`;img.id='camera-preview';screen.append(img);}
function renderState(){if(!state)return;
 const mode=document.querySelector('#mode');if(mode)mode.textContent=state.quiet?'QUIET · reminders muted':state.meeting_active?'POSSIBLE MEETING · deferred':state.demo?'DEMO · shortened timers':'LOCAL · camera stays on this device';
 if(page==='home'){
  text('30:173',state.camera);if(!$('30:174'))return;$('30:174').style.background=state.camera.startsWith('Camera active')?'#2fff00':'#888';text('30:175',duration(state.active_seconds));
  text('30:164',state.phase==='paused'?'Resume':'Pause');$('30:164').style.left=state.phase==='paused'?'900px':'924px';
  screen.startButton.disabled=['running','paused'].includes(state.phase);screen.pauseButton.disabled=!['running','paused'].includes(state.phase);screen.endButton.disabled=!['running','paused'].includes(state.phase);
  const near=state.posture==='NEAR_REFERENCE',low=state.posture==='LOWER_HEAD_POSITION';text('53:204',near?'Near':low?'Lower':'Unknown');$('53:204').style.fontSize='11px';$('53:204').style.left='526px';$('53:205').style.background=near?'#2df600':low?'#a85b00':'#666';
  const badge=v=>({'Calibration required':'Calibrate','Near reference':'Near','Waiting for observation':'Waiting','Watching eye closure':'Watching','Already notified':'Notified','Warming up':'Warm-up','Not observed':'Unknown'}[v]||v);text('53:210',state.config.distance.enabled?badge(state.distance):'Off');text('53:213',state.config.fatigue.enabled?badge(state.fatigue):'Off');$('53:210').title=state.distance;$('53:213').title=state.fatigue;
  text('53:339',state.near_percent===null?'—':`${state.near_percent}%`);text('53:366',duration(state.longest_streak));$('53:366').style.fontSize='35px';$('53:366').style.top='665px';
 }
 if(page==='camera'){text('123:1444',state.last_calibration?'Last calibrated: '+new Date(state.last_calibration).toLocaleTimeString():'No calibration in this app session');$('123:1444').style.left='610px';}
 if(page==='calibration'){
  document.querySelector('#cal-status').textContent=state.error||state.calibration_message;document.querySelector('#cal-progress').style.width=(1294*state.calibration_progress)+'px';screen.calButton.disabled=state.calibrating;
 }
 if(modalRefresh)modalRefresh();
}
let lastError='';async function poll(){if(pollBusy)return;pollBusy=true;try{state=await api('api/state');document.body.classList.remove('disconnected');const issue=state.error||state.vision_error;if(issue&&issue!==lastError)notify(issue);lastError=issue;renderState();}catch(e){document.body.classList.add('disconnected');notify('Sora is not connected. Reopen Start Sora UI to reconnect.');}finally{pollBusy=false;}}
async function cameraTick(){const img=document.querySelector('#details[open] #debug-camera')||document.querySelector('#camera-preview');if(!img||cameraBusy)return;cameraBusy=true;try{const r=await fetch('api/camera');if(r.status===200){const blob=await r.blob();if(!img.isConnected||img.dataset.closed==='true')return;const url=URL.createObjectURL(blob);const old=img.src;img.onload=()=>{if(old.startsWith('blob:'))URL.revokeObjectURL(old);};img.src=url;img.hidden=false;}else{img.hidden=true;}}catch{}finally{cameraBusy=false;}}
function showCamera(){
 if(document.querySelector('#details[open] #debug-camera'))return;
 modal('Camera preview',c=>{
  const status=document.createElement('p');status.setAttribute('role','status');c.append(status);
  const img=document.createElement('img');img.id='debug-camera';img.className='debug-camera';img.alt='Live mirrored camera with upper-body tracking';img.hidden=true;c.append(img);
  const stats=document.createElement('p');stats.className='camera-debug-stats';c.append(stats);
  const hint=document.createElement('p');hint.textContent='Closing this view keeps detection running during a session. In preview-only mode, closing it releases the camera.';c.append(hint);
  button('Close camera view',()=>document.querySelector('#details').close(),c);
  modalRefresh=()=>{status.textContent=state.error||state.camera;stats.textContent=`Posture: ${state.posture.replaceAll('_',' ')} | FPS: ${state.fps} | ${state.phase==='running'?'Session running':'Preview only - no session time counted'}`;};modalRefresh();
  modalCleanup=()=>{img.dataset.closed='true';if(img.src.startsWith('blob:'))URL.revokeObjectURL(img.src);action('close_debug_preview');};
 });
 action('open_debug_preview').then(ok=>{if(ok)cameraTick();});
}
function showAgent(){modal('Agent activity',c=>{const body=document.createElement('div');c.append(body);modalRefresh=()=>{body.replaceChildren();for(const value of [state.agent.status,state.agent.cloud,state.meeting,state.ignore_meeting?'Meeting override: ON':'Meeting override: OFF','Head orientation: '+state.orientation+' (not gaze tracking)']){const p=document.createElement('p');p.textContent=value;body.append(p);}for(const e of state.agent.trace.slice(-12).reverse()){const p=document.createElement('pre');p.style.cssText='white-space:pre-wrap;font-size:12px';p.textContent=JSON.stringify(e,null,2);body.append(p);}};modalRefresh();button('Toggle meeting override',()=>action('ignore_meeting'),c);button('Download recent trace',()=>{const a=document.createElement('a');const url=URL.createObjectURL(new Blob([state.agent.trace.map(e=>JSON.stringify(e)).join('\n')],{type:'application/x-ndjson'}));a.href=url;a.download='sora-agent-trace.jsonl';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);},c);});}
function showTimers(){modal('Session reminders',c=>{const list=document.createElement('div');c.append(list);modalRefresh=()=>{list.replaceChildren();for(const [name,t]of Object.entries(state.timers)){const p=document.createElement('div');p.className='row';p.textContent=`${name==='sleep'?'Session limit':name}: ${t.enabled?duration(t.remaining)+' remaining':'Off'}`;list.append(p);}const status=document.createElement('p');status.textContent=state.drinking_status+' · '+state.drink_count+' recorded drinks';list.append(status);if(state.in_break){const p=document.createElement('p');p.textContent='Break: '+duration(state.break_remaining)+' remaining';list.append(p);}};modalRefresh();const details=document.createElement('p');details.textContent=state.drinking_status+' · '+state.drink_count+' recorded events';c.append(details);button('I drank',()=>action('drink'),c);button('Undo automatic sip',()=>action('undo_drink'),c);button(state.quiet?'Turn quiet mode off':'Quiet mode (mute reminders)',()=>action('quiet'),c);button('Show camera & calibration',()=>{document.querySelector('#details').close();navigate('camera');},c);button('I moved',()=>action('move'),c);button('Start / resume break',()=>action(state.in_break?'resume_break':'break'),c);const p=document.createElement('p');p.textContent='Water uses elapsed unpaused time. Movement, screen breaks and session limit use observed presence. Likely sips can be estimated automatically. Confirm manually if missed; undo if incorrect. Quiet mode mutes reminders while observations continue.';c.append(p);});}
async function updateHistory(){const h=await api('api/history');if(page!=='history')return;screen.querySelectorAll('#activity-list,.chart,.empty-chart').forEach(e=>e.remove());text('52:174',h.near_percent===null?'—':h.near_percent+'%');text('50:1000','Time near reference');text('52:173','Of usable observations');text('50:977',String(Math.floor(h.active_seconds/3600)).padStart(2,'0'));text('50:978',String(Math.floor(h.active_seconds/60)%60).padStart(2,'0'));text('52:181',h.completed_breaks+'x');text('44:444','Observed presence · minutes per hour');$('44:444').style.fontSize='23px';
 $('50:979').style.left='1115px';$('50:978').style.left='1180px';$('50:980').style.left='1250px';
 ['48:485','48:486'].forEach(id=>{$(id)?.remove();});const list=document.createElement('div');list.id='activity-list';screen.append(list);const ev=h.events.filter(e=>e.event!=='processing_gap_excluded').slice(0,2);if(!ev.length)list.textContent='No activity yet. Start a session to build your history.';for(const e of ev)eventRow(e,list);
 const chart=document.createElement('div');chart.className='chart';h.hours.forEach((v,i)=>{const b=document.createElement('div');b.style.height=(Math.min(60,v/60)/60*100)+'%';b.title=`${String(i).padStart(2,'0')}:00 — ${(v/60).toFixed(1)} min`;chart.append(b);});screen.append(chart);
 ['44:445','44:446','44:449','44:458','44:465','44:466','44:467'].forEach((id,i)=>text(id,['00:00','04:00','08:00','12:00','16:00','20:00','24:00'][i]));
 if(!h.hours.some(v=>v>0)){const p=document.createElement('p');p.className='empty-chart';p.textContent='No observed time recorded today';screen.append(p);}
}
function eventRow(e,parent){const row=document.createElement('div');row.className='event';const t=document.createElement('time');t.textContent=new Date(e.time).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});const d=document.createElement('div');d.textContent=e.event.replaceAll('_',' ');const small=document.createElement('small');small.textContent=Object.entries(e.details||{}).map(([k,v])=>`${k.replaceAll('_',' ')}: ${v}`).join(' · ');d.append(small);row.append(t,d);parent.append(row);}
async function showHistory(){try{const h=await api('api/history');modal('Today’s activity',c=>{if(!h.events.length)c.append('No activity yet.');h.events.forEach(e=>eventRow(e,c));});}catch(e){notify(e.message);}}
(async()=>{await poll();if(state)await navigate('home');setInterval(poll,750);setInterval(cameraTick,400);setInterval(()=>{if(page==='history')updateHistory().catch(()=>{});},5000);})();
