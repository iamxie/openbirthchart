const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
(async()=>{
 const root=path.resolve(process.argv[2]),browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const context=await browser.newContext({offline:true}),page=await context.newPage(),errors=[],external=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url())});
  const widths=[];
  for(const width of [1400,480,320]){
   await page.setViewportSize({width,height:900});await page.goto(pathToFileURL(path.join(root,'index.html')).href);
   if(await page.locator('#changes tbody tr').count()!==2351)throw Error('Missing rows');
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Page overflow');widths.push(width);
  }
  await page.locator('#suite').selectOption('complete');if(await page.locator('tbody tr:visible').count()!==1397)throw Error('Complete filter');
  await page.locator('#search').fill('智神星');if(await page.locator('tbody tr:visible').count()!==432)throw Error('Body filter');
  await page.locator('#suite').selectOption('legacy');if(await page.locator('tbody tr:visible').count()!==240)throw Error('Combined filter');
  await page.locator('#search').fill('complete-1904-01-H');await page.locator('#suite').selectOption('complete');
  const link=page.locator('tbody tr:visible a').first();await link.click();if(!await page.locator('.wheel svg').count())throw Error('Broken report link');
  await page.goto(pathToFileURL(path.join(root,'index.html')).href);await page.setViewportSize({width:1400,height:900});
  await page.screenshot({path:path.join(root,'index-preview.png')});
  if(errors.length||external.length)throw Error(JSON.stringify({errors,external}));
  fs.writeFileSync(path.join(root,'index-checks.json'),JSON.stringify({rows:2351,widths,filtersPassed:true,reportLinkPassed:true,errors,external},null,2));
  console.log('Searchable index verified: 2351 rows, filters, linked chart and 3 widths');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
