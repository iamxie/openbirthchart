const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
(async()=>{
 const root=path.resolve(process.argv[2]),folder=path.join(root,'exports');
 const expected=JSON.parse(fs.readFileSync(path.join(root,'export-checks.json'),'utf8'));
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const context=await browser.newContext({offline:true}),page=await context.newPage();
  const checks=[],external=[],errors=[];
  page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url())});page.on('pageerror',e=>errors.push(String(e)));
  for(const e of expected){
   const name=`${e.case}-${e.mode}-${e.language}`;
   for(const width of [1400,800,480,320]){
    await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(path.join(folder,name+'.html')).href);
    await page.evaluate(()=>document.fonts.ready);
    const r=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,
     positions:[...document.querySelectorAll('#positions tbody tr')].map(r=>r.cells[2].textContent),
     cusps:document.querySelectorAll('#houses tbody tr').length,
     wheel:document.querySelector('.wheel svg')?.getBoundingClientRect().width,
     title:document.querySelector('.wheel svg text')?.textContent}));
    const houses=e.table_houses.map(h=>h===null?(e.language==='en-US'?'Undefined':'未定義'):String(h));
    if(r.overflow||r.cusps!==12||!r.wheel||JSON.stringify(r.positions)!==JSON.stringify(houses))throw Error(name+JSON.stringify(r));
    checks.push({name,width,...r});
    if(width===1400||width===320)await page.locator('#chart').screenshot({path:path.join(folder,`${name}-browser-${width}.png`)});
   }
   await page.emulateMedia({media:'print'});
   await page.pdf({path:path.join(folder,name+'.pdf'),preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});
   await page.emulateMedia({media:'screen'});
   console.log(name+' checked');
  }
  if(external.length||errors.length)throw Error(JSON.stringify({external,errors}));
  fs.writeFileSync(path.join(root,'browser-checks.json'),JSON.stringify({checks,external,errors,pdfs:expected.length},null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
