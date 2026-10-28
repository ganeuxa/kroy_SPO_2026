// PLAYWRIGHT_MODULE may point to the installed Playwright package.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('fs');
(async()=>{
 fs.mkdirSync('qa-results',{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.QA_CHROMIUM});
 const page=await browser.newPage({viewport:{width:1280,height:800}});
 const base=process.env.QA_UI_URL||'http://127.0.0.1:15173';const results=[];
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function test(name,fn){try{await fn();results.push({test:name,status:'PASS'})}catch(e){results.push({test:name,status:'FAIL',detail:e.message})}console.log(results.at(-1))}
 async function visible(loc){await loc.waitFor({state:'visible',timeout:10000})}
 async function shot(name){await page.screenshot({path:`qa-results/${name}.png`,fullPage:true})}
 await test('Catalog renders',async()=>{await page.goto(base);await visible(page.locator('.card').first());await shot('01-catalog')});
 await test('Guest cart protected',async()=>{await page.goto(base+'/cart');await visible(page.getByText('Чтобы пользоваться корзиной, войдите в аккаунт.'));await shot('02-guest-cart')});
 await test('Registration validation',async()=>{await page.goto(base+'/register');await page.getByRole('button',{name:'Зарегистрироваться',exact:true}).click();await visible(page.getByText('Укажите имя'));await visible(page.getByText('Неверный email'));await shot('03-validation')});
 await test('Registration and automatic login',async()=>{
  await page.locator('input[autocomplete="name"]').fill('Варя QA');await page.locator('input[autocomplete="email"]').fill('qa-ui-'+Date.now()+'@example.com');
  await page.locator('input[autocomplete="new-password"]').first().fill('Qa-Strong-2026');await page.locator('input[autocomplete="new-password"]').nth(1).fill('Qa-Strong-2026');
  await page.getByRole('button',{name:'Зарегистрироваться',exact:true}).click();await visible(page.getByRole('button',{name:'Выйти'}));
 });
 await test('Empty cart',async()=>{await page.goto(base+'/cart');await visible(page.getByText('Корзина пуста'))});
 await test('Select size and add to cart',async()=>{await page.goto(base+'/products/1');await visible(page.getByRole('heading',{level:1}));const add=page.getByRole('button',{name:'В корзину',exact:true});if(!await add.isDisabled())throw Error('Add enabled without size');await page.locator('.option').nth(1).locator('button:not([disabled])').first().click();await add.click();await visible(page.getByRole('status'));await shot('04-added');await page.getByRole('link',{name:'Перейти в корзину',exact:true}).click();await visible(page.locator('.cart__item'));await shot('05-cart')});
 await test('Session and cart survive reload',async()=>{await page.reload();await visible(page.locator('.cart__item'));await visible(page.getByRole('button',{name:'Выйти'}))});
 await test('Logout closes cart',async()=>{await page.getByRole('button',{name:'Выйти'}).click();await visible(page.getByText('Чтобы пользоваться корзиной, войдите в аккаунт.'))});
 await test('Wrong login error',async()=>{await page.goto(base+'/login');await page.getByLabel('Email').fill('anna@example.com');await page.getByLabel('Пароль').fill('wrong');await page.getByRole('button',{name:'Войти',exact:true}).click();await visible(page.getByRole('alert'));await shot('06-login-error')});
 await test('Login returns to cart',async()=>{await page.goto(base+'/login?next=/cart');await page.getByLabel('Email').fill('ilya@example.com');await page.getByLabel('Пароль').fill('KroyTest-2026');await page.getByRole('button',{name:'Войти',exact:true}).click();await visible(page.locator('.cart__item').first());if(!page.url().endsWith('/cart'))throw Error(page.url())});
 await test('Mobile catalog no overflow',async()=>{await page.setViewportSize({width:360,height:800});await page.goto(base);await visible(page.locator('.card').first());if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');await shot('07-mobile')});
 await test('No uncaught browser errors',async()=>{if(errors.length)throw Error(errors.join('\n'))});
 fs.writeFileSync('qa-results/ui.json',JSON.stringify(results,null,2));await browser.close();process.exitCode=results.some(x=>x.status==='FAIL')?1:0;
})().catch(e=>{console.error(e);process.exitCode=1});
