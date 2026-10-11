import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const $=id=>document.getElementById(id);
try {
const data=await (await fetch('./manifest.json')).json();$('title').textContent=data.title;
$('status').textContent=`Visual approval: ${typeof data.visual_approval==='string'?data.visual_approval:data.visual_approval.status}. Automated checks and visual approval are recorded separately.`;
for(const c of data.checks){const li=document.createElement('li');li.className=c.ok?'pass':'fail';li.textContent=`${c.ok?'PASS':'FAIL'} · ${c.text} ${c.detail||''}`;$('checks').append(li);}
$('scores').textContent=JSON.stringify(data.fit_scores,null,2);
function figure(item,label){const f=document.createElement('figure'),img=document.createElement('img'),caption=document.createElement('figcaption'),a=document.createElement('a');img.src=item.url;img.alt=label;img.loading='lazy';a.href=item.url;a.target='_blank';a.rel='noopener';a.append(img);caption.textContent=label;f.append(a,caption);return f;}
for(const r of data.references)$('references').append(figure(r,`${r.source.toUpperCase()} · ${r.view||'reference'} · ${r.review_status||'unreviewed'}`));
for(const region of [...new Set(data.shots.map(s=>s.region))])$('region').add(new Option(region,region));
function shots(){ $('shots').replaceChildren();for(const s of data.shots.filter(s=>!$('region').value||s.region===$('region').value))$('shots').append(figure(s,`${s.stale?'STALE · ':''}${s.region} · ${s.pose} · ${s.mode} · ${s.view}`)); }shots();$('region').onchange=shots;
if(data.workflow && data.workflow.status!=='disabled'){
  $('guided-review').hidden=false;
  $('workflow-summary').textContent=`${data.workflow.status} · ${data.workflow.current_stage||'All stages reviewed'} · ${data.workflow.next_action}`;
  for(const s of data.workflow.stages){const li=document.createElement('li');li.className=s.status==='accepted'?'pass':'fail';li.textContent=`${s.id}: ${s.status} · ${s.next_action}`;$('workflow-stages').append(li);}
  for(const f of data.workflow.features){
    const card=document.createElement('article'),heading=document.createElement('h3'),detail=document.createElement('p'),note=document.createElement('p'),button=document.createElement('button');
    heading.textContent=f.description;detail.textContent=`${f.id} · ${f.stage} · ${f.status} · ${f.basis.toUpperCase()} · ${f.required===false?'optional':'required'}`;
    note.textContent=[f.notes,f.note,f.evidence_issue].filter(Boolean).join(' · ');button.textContent='Show model close-ups';button.onclick=()=>{$('region').value='feature-'+f.id;shots();$('shots').scrollIntoView({behavior:'smooth'});};
    card.append(heading,detail,note,button);
    const gallery=document.createElement('div');gallery.className='gallery';for(const r of (data.feature_references||[]).filter(r=>r.feature_id===f.id))gallery.append(figure(r,`${r.source.toUpperCase()} · ${r.view}`));card.append(gallery);$('features').append(card);
  }
}
const host=$('viewport'),renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor(0xc4cfce);renderer.outputColorSpace=THREE.SRGBColorSpace;host.append(renderer.domElement);
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.001,1000),controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
scene.add(new THREE.HemisphereLight(0xffffff,0x6c7880,2.2));const light=new THREE.DirectionalLight(0xffffff,2.5);light.position.set(3,5,4);scene.add(light);
let object=null,mixer=null,action=null,clips=[],playing=false,span=1,target=new THREE.Vector3(),helpers=[];const loader=new GLTFLoader();
const checkerCanvas=document.createElement('canvas');checkerCanvas.width=checkerCanvas.height=128;const ctx=checkerCanvas.getContext('2d');for(let y=0;y<8;y++)for(let x=0;x<8;x++){ctx.fillStyle=(x+y)%2?'#222':'#eee';ctx.fillRect(x*16,y*16,16,16);}const checker=new THREE.CanvasTexture(checkerCanvas);checker.wrapS=checker.wrapT=THREE.RepeatWrapping;checker.repeat.set(4,4);
function view(){const angles={front:[0,0],back:[Math.PI,0],side:[-Math.PI/2,0],quarter:[.65,.35],top:[0,1.52],below:[.5,-1.15]},[a,e]=angles[$('view').value],d=span*2.4;camera.position.copy(target).add(new THREE.Vector3(Math.sin(a)*Math.cos(e),Math.sin(e),Math.cos(a)*Math.cos(e)).multiplyScalar(d));controls.target.copy(target);controls.update();} $('view').onchange=view;
function mode(){if(!object)return;object.traverse(o=>{if(!o.isMesh)return;const bases=o.userData.baseMaterials;for(const old of [].concat(o.material))if(!bases.includes(old))old.dispose();const materials=bases.map(base=>{const m=base.clone();m.wireframe=$('mode').value==='wireframe';if($('mode').value==='plain'){m.map=null;m.color.set(0x8da5b2);}if($('mode').value==='checker'){m.map=checker;m.color.set(0xffffff);}return m;});o.material=materials.length===1?materials[0]:materials;});} $('mode').onchange=mode;
async function load(i){if(object){scene.remove(object);object.traverse(o=>{if(o.isMesh){o.geometry.dispose();for(const m of [].concat(o.material))m.dispose();}});}for(const h of helpers)h.removeFromParent();helpers=[];
const item=data.outputs[i],g=await loader.loadAsync(item.url);object=g.scene;scene.add(object);object.traverse(o=>{if(o.isMesh)o.userData.baseMaterials=[].concat(o.material);if(o.name.startsWith('socket_')){const axes=new THREE.AxesHelper(.12);axes.visible=$('sockets').checked;o.add(axes);helpers.push(axes);}});
const box=new THREE.Box3().setFromObject(object);box.getCenter(target);span=Math.max(...box.getSize(new THREE.Vector3()).toArray(),.01);camera.near=Math.max(span/10000,.0001);camera.far=span*1000;camera.updateProjectionMatrix();view();mode();mixer=new THREE.AnimationMixer(object);clips=g.animations;$('clip').replaceChildren(new Option('Rest',''));for(let j=0;j<clips.length;j++)$('clip').add(new Option(clips[j].name,String(j)));action=null;playing=false;$('play').textContent='Play';$('time').value=0;$('model-info').textContent=`${item.label} · SHA-256 ${item.sha256}`;
}
$('clip').onchange=()=>{mixer.stopAllAction();action=$('clip').value===''?null:mixer.clipAction(clips[Number($('clip').value)]);if(action){action.reset().play();action.paused=!playing;} $('time').value=0;};
$('play').onclick=()=>{playing=!playing;if(action)action.paused=!playing;$('play').textContent=playing?'Pause':'Play';};$('time').oninput=()=>{if(action){action.time=Number($('time').value)*action.getClip().duration;mixer.update(0);}};
$('sockets').onchange=()=>{for(const h of helpers)h.visible=$('sockets').checked;};
for(let i=0;i<data.outputs.length;i++)$('model').add(new Option(data.outputs[i].label,String(i)));$('model').onchange=()=>load(Number($('model').value)).catch(fail);
const ro=new ResizeObserver(()=>{renderer.setSize(host.clientWidth,host.clientHeight);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();});ro.observe(host);
let last=performance.now();renderer.setAnimationLoop(now=>{const dt=Math.min((now-last)/1000,.1);last=now;if(mixer)mixer.update(dt);if(action&&playing)$('time').value=action.time/action.getClip().duration;controls.update();renderer.render(scene,camera);});
if(data.outputs.length)await load(0);else throw Error('Build a model before opening the review page.');
} catch(e){fail(e);}
function fail(e){$('error').textContent=e.message;console.error(e);}
