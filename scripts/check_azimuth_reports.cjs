// Render the actual portable export offline in Edge, including print and anchors.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('fs'), path=require('path'),{pathToFileURL}=require('url');
(async()=>{
 const folder=path.resolve(process.argv[2]);
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try {
  const context=await browser.newContext({offline:true});const page=await context.newPage();const external=[],errors=[],results=[];
  page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url())});page.on('pageerror',e=>errors.push(String(e)));
  for(const lang of ['zh-TW','en-US']){
   const name='report-'+lang;
   for(const width of [1300,800,480,320]){
    await page.setViewportSize({width,height:900});await page.goto(pathToFileURL(path.join(folder,name+'.html')).href);await page.evaluate(()=>document.fonts.ready);
    const before=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,notices:document.querySelectorAll('[role="note"]').length,sections:document.querySelectorAll('main>section.page').length}));
    if(before.overflow||before.notices!==2||before.sections!==6)throw Error(JSON.stringify(before));
    if(width===1300||width===320)await page.screenshot({path:path.join(folder,name+'-'+width+'.png'),fullPage:true});
    await page.locator('#chart .house-notice a').click();
    const anchor=await page.evaluate(()=>({heading:document.querySelector('#azimuth-help h1').getBoundingClientRect().top,header:document.querySelector('header').getBoundingClientRect().bottom}));
    if(anchor.heading<anchor.header-1)throw Error(JSON.stringify(anchor));
    results.push({lang,width,...before,anchor});
   }
   await page.emulateMedia({media:'print'});
   if(!await page.locator('.house-notice').evaluateAll(xs=>xs.every(e=>getComputedStyle(e).display!=='none')))throw Error('Print notice hidden');
   await page.pdf({path:path.join(folder,name+'.pdf'),preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});
   await page.emulateMedia({media:'screen'});
  }
  if(external.length||errors.length)throw Error(JSON.stringify({external,errors}));
  fs.writeFileSync(path.join(folder,'azimuth-browser-checks.json'),JSON.stringify({results,external,errors},null,2));console.log('Eight responsive checks; both PDF exports generated offline.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
