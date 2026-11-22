const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const { chromium } = require("playwright");

const base="http://127.0.0.1:8766";
const wait = ms => new Promise(resolve=>setTimeout(resolve,ms));

async function main(){
 const server=spawn("python3",["server.py","--host","127.0.0.1","--port","8766"],{stdio:"inherit"});
 let browser;
 try {
  let available=false;
  for(let i=0;i<90;i++){
   try{const result=await fetch(base+"/api/health");if(result.ok){available=true;break}}catch{}
   await wait(300);
  }
  assert(available,"Development server failed to start");
  browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
  const context=await browser.newContext({viewport:{width:1280,height:850},timezoneId:"Asia/Manila"});
  const home=await context.newPage();
  await home.goto(base+"/",{waitUntil:"domcontentloaded"});
  assert.equal(await home.locator(".roles .role").count(),3,"Three role choices required");
  assert.deepEqual(await home.locator(".roles .role").evaluateAll(nodes=>nodes.map(n=>n.getAttribute("href"))),["/student","/guard","/admin"]);
  await home.screenshot({path:"homepage-audit.png",fullPage:true});

  const board=await context.newPage();
  await board.goto(base+"/flowboard",{waitUntil:"domcontentloaded"});
  assert.equal(await board.locator("#stage .node").count(),20,"Flowboard screen count");
  assert.equal(await board.locator("#links path.edge").count(),31,"Directed arrow count");
  assert.equal(await board.locator("#node-H00_home iframe").count(),1,"Homepage preview must be an actual page");
  await board.frameLocator("#node-H00_home iframe").locator(".roles .role").first().waitFor({timeout:15000});
  await board.locator("#node-H00_home").click();
  assert(await board.locator("#info").evaluate(n=>n.classList.contains("visible")),"Home details must open");
  await board.locator("#showScreen").click();
  assert(await board.locator("#lightHome").isVisible(),"Homepage preview lightbox must open");
  await board.locator("#lightbox button").click();
  await board.screenshot({path:"flowboard-audit.png"});

  const student=await context.newPage(),guard=await context.newPage(),admin=await context.newPage();
  async function login(page,path,user,password){
   await page.goto(base+path,{waitUntil:"domcontentloaded"});
   assert.deepEqual(await page.locator(".hub-nav a").allTextContents(),["Home"],"Role navigation must only return Home");
   if(path==="/student"){await page.locator("#studentUser").fill(user);await page.locator("#studentPass").fill(password);await page.locator('[data-action="student-sign-in"]').click();}
   else{await page.locator("#staffUser").fill(user);await page.locator("#staffPass").fill(password);await page.locator('[data-action="sign-in"]').click();}
  }
  await login(student,"/student","202600001","DemoStudent#26");
  await student.locator(".big-number").waitFor({timeout:15000});
  assert.equal((await student.locator(".big-number").innerText()).trim(),"14","Starting available count");
  await login(guard,"/guard","guard.demo","DemoGuard#26");
  await guard.locator('[data-select="S-12"]').waitFor({timeout:15000});
  await login(admin,"/admin","admin.demo","DemoAdmin#26");
  await admin.locator(".metric strong").first().waitFor({timeout:15000});
  await guard.locator('[data-select="S-12"]').click();
  await guard.locator('#dialogRoot [data-set="occupied"][data-space="S-12"]').click();
  await student.waitForFunction(()=>document.querySelector(".big-number")?.textContent.trim()==="13",null,{timeout:15000});
  await admin.waitForFunction(()=>document.querySelector(".metric strong")?.textContent.trim()==="21 / 34",null,{timeout:15000});
  await guard.waitForFunction(()=>document.querySelector(".mini-count strong")?.textContent.trim()==="21 / 34",null,{timeout:15000});

  await admin.locator('[data-admin="verify"]').first().click();
  await admin.locator("#correctSpace").selectOption("S-12");
  await admin.locator("#correctTo").selectOption("available");
  await admin.locator("#correctReason").fill("Verified current physical status during regression audit");
  await admin.locator('[data-action="correction-preview"]').click();
  await admin.locator("#ackCorrection").check({timeout:5000});
  await admin.locator('[data-action="correction-approve"]').click();
  await student.waitForFunction(()=>document.querySelector(".big-number")?.textContent.trim()==="14",null,{timeout:15000});
  await guard.waitForFunction(()=>document.querySelector(".mini-count strong")?.textContent.trim()==="20 / 34",null,{timeout:15000});
  await admin.locator('[data-admin="overview"]').first().click();
  await admin.waitForFunction(()=>document.querySelector(".metric strong")?.textContent.trim()==="20 / 34",null,{timeout:15000});
  console.log("PASS browser: Home+role navigation, 20 nodes, 31 arrows, Guard 20->21, Admin 21->20, all views agree");
 } finally {
  if(browser)await browser.close();
  server.kill("SIGTERM");
 }
}
main().catch(error=>{console.error(error);process.exitCode=1});
