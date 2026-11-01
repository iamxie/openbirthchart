// Real browser layout, offline resource and print verification (no external sites).
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('fs');const path=require('path');const {pathToFileURL}=require('url');
(async()=>{
 const dir=path.resolve(process.argv[2]);
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1300,height:900},offline:true});
  const page=await context.newPage();let external=[],errors=[];
  page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url())});
  page.on('pageerror',e=>errors.push(String(e)));
  const files=process.argv.slice(3);if(!files.length)files.push('report');
  const results=[];
  for(const file of files){
   await page.goto(pathToFileURL(path.join(dir,file+'.html')).href);await page.evaluate(()=>document.fonts.ready);
   await page.screenshot({path:path.join(dir,file+'-browser.png'),fullPage:true});
   const check=await page.evaluate(()=>({sections:document.querySelectorAll('main > section.page').length,
    tables:[...document.querySelectorAll('table')].map(t=>({rows:t.tBodies[0].rows.length,columns:t.tHead.rows[0].cells.length})),
    overflow:document.documentElement.scrollWidth>innerWidth,font:getComputedStyle(document.body).fontFamily,
    images:[...document.querySelectorAll('.wheel svg')].map(s=>({width:s.getBoundingClientRect().width,height:s.getBoundingClientRect().height})),
    counts:[...document.querySelectorAll('main > section.page')].map(s=>s.textContent.length)}));
   if(check.sections!==5||check.overflow||!check.font.includes('Microsoft JhengHei')||check.images.some(x=>!x.width||!x.height))throw Error(JSON.stringify(check));
   await page.locator('nav a[href="#positions"]').click();
   const anchor=await page.evaluate(()=>({navBottom:document.querySelector('header').getBoundingClientRect().bottom,
    targetTop:document.querySelector('#positions h1').getBoundingClientRect().top,sticky:getComputedStyle(document.querySelector('header')).position}));
   if(anchor.sticky!=='sticky'||anchor.targetTop<anchor.navBottom)throw Error('Navigation obscures heading '+JSON.stringify(anchor));
   check.anchor=anchor;
   await page.emulateMedia({media:'print'});
   const printHidden=await page.locator('.screen-only').evaluateAll(elements=>elements.every(e=>getComputedStyle(e).display==='none'));
   if(!printHidden)throw Error('Screen chrome appears in print');
   await page.pdf({path:path.join(dir,file+'-print.pdf'),preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});
   await page.emulateMedia({media:'screen'});
   results.push({file,...check});
  }
  if(external.length||errors.length)throw Error(JSON.stringify({external,errors}));
  fs.writeFileSync(path.join(dir,'browser-checks.json'),JSON.stringify({results,external,errors},null,2));console.log(JSON.stringify(results));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
