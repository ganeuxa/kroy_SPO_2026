const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.QA_CHROMIUM});
 const page=await browser.newPage();const base='http://127.0.0.1:18080';const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const email='qa-ui3-'+Date.now()+'@example.com';
 async function login(email,password){await page.goto(base+'/login');await page.getByLabel('Email').fill(email);await page.getByLabel('Пароль').fill(password);await page.getByRole('button',{name:'Войти',exact:true}).click();await page.getByRole('button',{name:'Выйти'}).waitFor();}
 try {
 await page.goto(base+'/register');await page.locator('input[autocomplete="name"]').fill('QA UI');await page.locator('input[autocomplete="email"]').fill(email);await page.locator('input[autocomplete="new-password"]').first().fill('Qa-Strong-2026');await page.locator('input[autocomplete="new-password"]').nth(1).fill('Qa-Strong-2026');await page.getByRole('button',{name:'Зарегистрироваться',exact:true}).click();await page.getByRole('button',{name:'Выйти'}).waitFor();
 await page.goto(base+'/products/1');await page.locator('.option').nth(1).locator('button:not([disabled])').first().click();await page.getByRole('button',{name:'В корзину',exact:true}).click();await page.getByRole('status').waitFor();
 await page.goto(base+'/cart');await page.getByLabel('Увеличить количество',{exact:true}).click();await page.getByRole('link',{name:'Оформить заказ',exact:true}).click();await page.getByLabel('Телефон для связи').fill('+79990005678');await page.getByRole('button',{name:'Подтвердить заказ'}).click();await page.waitForURL(/\/orders\/\d+$/);const orderUrl=page.url();
 await page.screenshot({path:'qa-results/stage3-checkout.png',fullPage:true});
 await page.getByRole('button',{name:'Оплатить тестовым платежом'}).click();await page.getByRole('button',{name:'Оплатить',exact:true}).click();await page.getByRole('link',{name:'Вернуться к заказу'}).click();await page.locator('.status-pill--paid').waitFor();await page.screenshot({path:'qa-results/stage3-paid.png',fullPage:true});
 await page.goto(base+'/account/orders');await page.getByRole('link').filter({hasText:'Заказ №'}).first().waitFor();
 await page.getByRole('button',{name:'Выйти'}).click();await login('admin@kroy.test','KroyAdmin-2026');
 await page.goto(orderUrl.replace('/orders/','/admin/orders/'));await page.getByLabel('Новый статус').selectOption('shipped');await page.getByRole('button',{name:'Сохранить статус'}).click();await page.locator('.status-pill--shipped').waitFor();await page.screenshot({path:'qa-results/stage3-admin.png',fullPage:true});
 await page.setViewportSize({width:360,height:800});await page.goto(base+'/account/orders');await page.getByRole('heading',{level:1}).waitFor();if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
 if(errors.length)throw Error(errors.join('\n'));console.log('PASS: registration, cart quantity, checkout, payment, history, admin shipment, mobile, no JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
