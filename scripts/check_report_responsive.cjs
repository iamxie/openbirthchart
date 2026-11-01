const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const {pathToFileURL}=require('url');
const path=require('path');const fs=require('fs');
(async()=>{
 const dir=path.resolve(process.argv[2]);
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const page=await browser.newPage({offline:true});const checks=[];
  for(const width of [1300,800,480,320]){
   await page.setViewportSize({width,height:900});
   await page.goto(pathToFileURL(path.join(dir,'report.html')).href);
   for(const target of ['positions','houses','matrix','details']){
    await page.locator(`nav a[href="#${target}"]`).click();
    const result=await page.evaluate(target=>({width:innerWidth,target,
     overflow:document.documentElement.scrollWidth>innerWidth,
     headerBottom:document.querySelector('header').getBoundingClientRect().bottom,
     sectionTop:document.getElementById(target).getBoundingClientRect().top}),target);
    if(result.overflow||result.sectionTop<result.headerBottom-1)throw Error(JSON.stringify(result));
    checks.push(result);
   }
  }
  fs.writeFileSync(path.join(dir,'responsive-checks.json'),JSON.stringify(checks,null,2));
  console.log(`${checks.length} anchor/viewport combinations passed, offline.`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
