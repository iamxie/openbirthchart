// Actual offline Edge HTML and print rendering for eight cases in both languages.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
(async()=>{
 const folder=path.resolve(process.argv[2]);
 const files=fs.readdirSync(folder).filter(x=>x.endsWith('.html')).sort();
 if(files.length!==16)throw Error('Expected eight bilingual reports');
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const context=await browser.newContext({offline:true});const page=await context.newPage();
  const external=[],errors=[],checks=[];
  page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url())});
  page.on('pageerror',e=>errors.push(String(e)));
  for(const file of files){
   for(const width of [1300,800,480,320]){
    await page.setViewportSize({width,height:900});await page.goto(pathToFileURL(path.join(folder,file)).href);
    await page.evaluate(()=>document.fonts.ready);
    const result=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,
      sections:document.querySelectorAll('main>section.page').length,
      houses:document.querySelector('#houses tbody')?.rows.length,
      svg:document.querySelector('.wheel svg')?.getBoundingClientRect().width}));
    if(result.overflow||result.sections!==5||!result.svg)throw Error(file+JSON.stringify(result));
    checks.push({file,width,...result});
    if(width===1300||width===320)await page.locator('#chart').screenshot({path:path.join(folder,file.replace('.html',`-browser-${width}.png`))});
   }
   await page.emulateMedia({media:'print'});
   await page.pdf({path:path.join(folder,file.replace('.html','.pdf')),preferCSSPageSize:true,printBackground:true,displayHeaderFooter:false});
   await page.emulateMedia({media:'screen'});
  }
  if(external.length||errors.length)throw Error(JSON.stringify({external,errors}));
  fs.writeFileSync(path.join(folder,'browser-checks.json'),JSON.stringify({checks,external,errors},null,2));
  console.log('64 responsive checks; 16 PDFs; offline requests and page errors: zero');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
