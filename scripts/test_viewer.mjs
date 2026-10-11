import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';
const url=process.argv[2],output=process.argv[3];
if(!url||!output)throw Error('Usage: node test_viewer.mjs LOCAL_URL SCREENSHOT_FOLDER');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
const page=await browser.newPage({viewport:{width:1200,height:900}}),errors=[],external=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
await page.route('**/*',route=>{const request=route.request().url();if(!request.startsWith(new URL(url).origin)&&!request.startsWith('data:')&&!request.startsWith('blob:')){external.push(request);route.abort();}else route.continue();});
await page.goto(url);
try{await page.waitForFunction(()=>document.querySelector('#model-info').textContent.includes('SHA-256'));}catch(e){throw Error(JSON.stringify({errors,external,visible:await page.locator('body').innerText()}));}
assert.equal(await page.locator('#error').textContent(),'');
for(const view of ['front','side','back','below','quarter']){await page.selectOption('#view',view);}
for(const mode of ['plain','checker','wireframe','textured']){await page.selectOption('#mode',mode);}
await page.check('#sockets');
const count=await page.locator('#clip option').count();
if(count>1){await page.selectOption('#clip',{index:1});await page.click('#play');await page.locator('#time').evaluate(e=>{e.value='0.5';e.dispatchEvent(new Event('input',{bubbles:true}));});await page.click('#play');}
const viewport=await page.locator('#viewport').screenshot({path:output+'/model.png'});
const visiblePixels=await page.evaluate(async base64=>{
 const blob=await (await fetch('data:image/png;base64,'+base64)).blob(),bitmap=await createImageBitmap(blob),canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;const context=canvas.getContext('2d');context.drawImage(bitmap,0,0);const pixels=context.getImageData(0,0,canvas.width,canvas.height).data;let count=0;for(let i=0;i<pixels.length;i+=4)if(Math.abs(pixels[i]-196)+Math.abs(pixels[i+1]-207)+Math.abs(pixels[i+2]-206)>70)count++;return count;
},viewport.toString('base64'));
assert(visiblePixels>500,'Model meshes must actually be visible, not only empty sockets');
await page.screenshot({path:output+'/desktop.png',fullPage:true});
await page.setViewportSize({width:390,height:844});await page.selectOption('#view','below');await page.screenshot({path:output+'/mobile.png',fullPage:false});
assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Mobile horizontal overflow');
assert.deepEqual(external,[],'External requests');assert.deepEqual(errors,[],'Browser errors');
console.log('VIEWER PASS',JSON.stringify({clips:count-1,externalRequests:external.length,errors:errors.length}));
} finally {await browser.close();}
