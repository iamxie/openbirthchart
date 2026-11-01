const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const {pathToFileURL}=require('url');const path=require('path');const fs=require('fs');
(async()=>{
 const dir=path.resolve(process.argv[2]);
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1180},offline:true});
  await page.goto(pathToFileURL(path.join(dir,'report.html')).href);
  await page.screenshot({path:path.join(dir,'paper-preview.png')});
  const check=await page.evaluate(()=>{
   const size=s=>parseFloat(getComputedStyle(document.querySelector(s)).fontSize);
   return {name:size('.identity-person dd'),birth:size('.identity-birth dd'),body:size('.meta-fields dd'),
    groups:document.querySelectorAll('.meta-group').length,
    wheelWidth:document.querySelector('.wheel').getBoundingClientRect().width,
    svgWidth:document.querySelector('.wheel svg').getBoundingClientRect().width,
    paper:getComputedStyle(document.body).backgroundImage};
  });
  if(!(check.name>check.birth&&check.birth>check.body&&check.body>=16&&check.groups===2))throw Error(JSON.stringify(check));
  if(check.svgWidth>check.wheelWidth+1)throw Error('SVG overflows chart column '+JSON.stringify(check));
  await page.setViewportSize({width:480,height:1000});
  await page.screenshot({path:path.join(dir,'paper-mobile.png'),fullPage:true});
  fs.writeFileSync(path.join(dir,'hierarchy-checks.json'),JSON.stringify(check,null,2));console.log(check);
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
