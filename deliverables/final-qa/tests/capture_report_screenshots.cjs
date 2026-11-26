// Run against a local QA database. Creates a test user and two test orders.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { randomUUID } = require("node:crypto");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const base = process.env.QA_URL || "http://127.0.0.1:5173";
const baseline = process.env.QA_BASELINE_URL;
const screenshotDir = process.env.QA_SCREENSHOTS;
const email = `qa-checkout-${randomUUID().slice(0, 8)}@example.com`;
const password = randomUUID();
const phone = "+79001112233";
const exact = (name) => ({ name, exact: true });
const heading = (page, name) => page.getByRole("heading", { name });
const button = (page, name) => page.getByRole("button", exact(name));
const link = (page, name) => page.getByRole("link", exact(name));
const money = (amount) => `Итого: ${Number(amount).toLocaleString("ru-RU")} ₽`;

function localUrl(url) {
  assert.match(new URL(url).hostname, /^(localhost|127\.0\.0\.1|\[::1\])$/,
    "Use a local QA instance");
}

async function screenshot(page, name, fullPage = false) {
  if (!screenshotDir) return;
  fs.mkdirSync(screenshotDir, { recursive: true });
  const output = path.join(screenshotDir, `${name}.png`);
  await page.emulateMedia({ reducedMotion: "reduce" });
  if (fullPage) await page.screenshot({ path: output, fullPage: true });
  else await page.locator("main").screenshot({ path: output });
}

async function checkWidth(page, screen) {
  const widths = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  assert.ok(widths.document <= widths.viewport, `${screen}: ${JSON.stringify(widths)}`);
}

async function register(page) {
  await page.goto(`${base}/register`);
  await checkWidth(page, "registration");
    await screenshot(page, `registration`, true);
  await page.locator('input[autocomplete="name"]').fill("Проверка интерфейса");
  await page.locator('input[autocomplete="email"]').fill(email);
  for (const input of await page.locator('input[autocomplete="new-password"]').all()) {
    await input.fill(password);
  }
  await button(page, "Зарегистрироваться").click();
  await page.getByRole("button", { name: /Выйти/ }).waitFor();
}

async function search(page, query) {
  const input = page.getByRole("searchbox", exact("Поиск товара"));
  await input.fill(query);
  await button(page, "Найти").click();
  await page.waitForURL((url) => url.searchParams.get("q") === query);
}

async function addVariant(page, product, variant) {
  await heading(page, product.name).waitFor();
  const [colors, sizes] = await page.locator(".option").all();
  await colors.getByRole("button", exact(variant.color)).click();
  await sizes.getByRole("button", exact(variant.size)).click();
  await button(page, "В корзину").click();
  await link(page, "Перейти в корзину").click();
  await heading(page, "Корзина").waitFor();
}

async function checkout(page, method) {
  await link(page, "Оформить заказ").click();
  await heading(page, "Оформление заказа").waitFor();
  await page.getByLabel("Телефон для связи").fill("123");
  if (method === "courier") {
    await page.getByRole("alert").filter({ hasText: "Не удалось загрузить пункты выдачи" }).waitFor();
    await Promise.all([
      page.waitForResponse((response) => response.url().endsWith("/api/pickup-points")),
      button(page, "Повторить загрузку").click(),
    ]);
    await page.getByRole("alert").filter({ hasText: "Не удалось загрузить пункты выдачи" }).waitFor();
    await page.getByRole("radio", exact("Доставка курьером")).check();
    await page.getByLabel("Адрес доставки").fill("Учебный город, Тестовая улица, дом 1");
  }
  await button(page, "Подтвердить заказ").click();
  await page.getByRole("alert").filter({ hasText: "Укажите телефон" }).waitFor();
  await page.getByLabel("Телефон для связи").fill(phone);
  await checkWidth(page, `checkout ${method}`);
    await screenshot(page, `checkout-${method}`, true);
  await button(page, "Подтвердить заказ").click();
  await page.waitForURL(/\/orders\/\d+$/);
  await page.locator(".status-pill--new").waitFor();
  await checkWidth(page, "new order");
  return Number(page.url().split("/").at(-1));
}

async function compare(browser, token, cart) {
  if (!screenshotDir || !baseline) return;
  const names = [[baseline, "before"], [base, "after"]];
  const shortage = { ...cart, items: cart.items.map((item) => ({ ...item, stock: 1 })) };
  for (const [url, suffix] of names) {
    const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });
    try {
      await page.addInitScript((value) => localStorage.setItem("kroy_token", value), token);
      const catalogHandler = (route) => route.fulfill({ status: 503, json: { detail: "Каталог временно недоступен" } });
      await page.route("**/api/products?*", catalogHandler);
      await page.goto(`${url}/?q=${encodeURIComponent("Футболка")}`);
      await page.getByText("Каталог временно недоступен").waitFor();
      assert.equal(await button(page, "Повторить загрузку").count(), suffix === "before" ? 0 : 1);
      await screenshot(page, `catalog-${suffix}`);
      await page.unroute("**/api/products?*", catalogHandler);
      const cartHandler = (route) => route.fulfill({ json: shortage });
      await page.route("**/api/cart", cartHandler);
      await page.goto(`${url}/cart`);
      await page.getByText("В наличии только 1 шт.").waitFor();
      assert.equal(await link(page, "Оформить заказ").count(), suffix === "before" ? 1 : 0);
      await screenshot(page, `cart-${suffix}`);
      if (suffix === "after") {
        await page.goto(`${url}/checkout`);
        await link(page, "Исправить количество в корзине").waitFor();
      }
      await page.unroute("**/api/cart", cartHandler);
      await page.route("**/api/pickup-points", (route) => route.fulfill({ json: [] }));
      await page.goto(`${url}/checkout`);
      await page.getByLabel("Пункт выдачи").waitFor();
      assert.equal(await button(page, "Подтвердить заказ").isEnabled(), suffix === "before");
      if (suffix === "after") await page.getByText(/Пунктов самовывоза пока нет/).waitFor();
      await screenshot(page, `checkout-${suffix}`);
    } finally {
      await page.close();
    }
  }
}

async function checkAdmin(browser, paidId) {
  const { QA_ADMIN_EMAIL, QA_ADMIN_PASSWORD } = process.env;
  if (!QA_ADMIN_EMAIL || !QA_ADMIN_PASSWORD) return;
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  page.setDefaultTimeout(10000);
  try {
    await page.goto(`${base}/login`);
    await screenshot(page, "login", true);
    await page.getByLabel("Email").fill(QA_ADMIN_EMAIL);
    await page.getByLabel("Пароль").fill(QA_ADMIN_PASSWORD);
    await button(page, "Войти").click();
    await link(page, "Админка").click();
    await heading(page, "Товары").waitFor();
    await page.locator(".order-card").first().waitFor();
    await checkWidth(page, "admin products");
    await screenshot(page, `admin-products`, true);
    await page.goto(`${base}/admin/orders`);
    await page.getByLabel("Email покупателя").fill(email);
    await page.getByLabel("Статус").selectOption("paid");
    const paidOrder = page.getByRole("link", { name: new RegExp(`Заказ №${paidId}`) });
    await paidOrder.waitFor();
    await checkWidth(page, "admin orders");
    await screenshot(page, `admin-orders`, true);
    await paidOrder.click();
    await checkWidth(page, "admin order details");
    await page.getByLabel("Новый статус").selectOption("shipped");
    await button(page, "Сохранить статус").click();
    await page.locator(".status-pill--shipped").waitFor();
    await screenshot(page, `admin-shipped`, true);
    console.log("PASS: browser admin filters and status update, width 390 px");
  } finally {
    await page.close();
  }
}

async function main() {
  localUrl(base);
  if (baseline) localUrl(baseline);
  const browser = await chromium.launch({ executablePath: process.env.QA_CHROMIUM, headless: true });
  const page = await browser.newPage({ viewport: { width: 360, height: 800 } });
  page.setDefaultTimeout(10000);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  try {
    await page.goto(`${base}/admin/products`);
    await heading(page, "Нужен вход").waitFor();
    assert.equal((await page.request.get(`${base}/api/admin/products`)).status(), 401);
    await register(page);
    const token = await page.evaluate(() => localStorage.getItem("kroy_token"));
    const headers = { Authorization: `Bearer ${token}` };
    await page.goto(`${base}/admin/products`);
    await heading(page, "Недостаточно прав").waitFor();
    await screenshot(page, `access-denied`, true);
    assert.equal(await link(page, "Админка").count(), 0);
    assert.equal((await page.request.get(`${base}/api/admin/products`, { headers })).status(), 403);
    await page.goto(`${base}/cart`);
    await heading(page, "Корзина пуста").waitFor();
    await screenshot(page, `cart-empty`, true);
    await page.goto(`${base}/account/orders`);
    await heading(page, "Заказов пока нет").waitFor();

    await page.goto(base);
    await search(page, "неттакоготовараqa");
    await page.getByText(/Ничего не найдено/).waitFor();
    const failedSearch = "**/api/products?*";
    let releaseRequest;
    const gate = new Promise((resolve) => { releaseRequest = resolve; });
    const failOnce = async (route) => {
      await gate;
      await route.abort("failed");
    };
    await page.route(failedSearch, failOnce);
    await search(page, "Футболка");
    try {
      await page.getByText("Загрузка…", { exact: true }).waitFor();
    } finally {
      releaseRequest();
    }
    await page.getByRole("alert").filter({ hasText: "Сервер недоступен" }).waitFor();
    await page.unroute(failedSearch, failOnce);
    const missingPhoto = "/media/qa-missing.png";
    await page.route(`**${missingPhoto}`, (route) => route.fulfill({ status: 404 }));
    await page.route(failedSearch, async (route) => {
      const response = await route.fetch();
      const results = await response.json();
      results.items[0].image_url = missingPhoto;
      await route.fulfill({ response, json: results });
    }, { times: 1 });
    await button(page, "Повторить загрузку").click();
    await page.getByText(/По запросу «Футболка».*Найдено/).waitFor();
    await page.locator(".card .shot").first().locator("svg").waitFor();
    await page.unroute(`**${missingPhoto}`);
    await checkWidth(page, "catalog");
    await screenshot(page, "catalog-mobile-after", true);

    const product = await (await page.request.get(`${base}/api/products/1`)).json();
    const variant = [...product.variants].sort((a, b) => b.stock - a.stock).find(({ stock }) => stock >= 3);
    assert.ok(variant, "The base T-shirt needs at least three units in QA");
    await page.locator(".card a").filter({ hasText: product.name }).click();
    await heading(page, product.name).waitFor();
    await checkWidth(page, "product");
    await screenshot(page, `product`, true);
    await addVariant(page, product, variant);
    await checkWidth(page, "cart");

    const increase = page.getByLabel("Увеличить количество");
    const failedPatch = "**/api/cart/items/*";
    await page.route(failedPatch, (route) => route.fulfill({ status: 503, json: { detail: "Тестовый сбой корзины" } }), { times: 1 });
    await increase.click();
    await page.getByRole("alert").filter({ hasText: "Тестовый сбой корзины" }).waitFor();
    await page.getByText(money(product.price), { exact: true }).waitFor();
    await increase.click();
    await page.getByText(money(Number(product.price) * 2), { exact: true }).waitFor();
    const cart = await (await page.request.get(`${base}/api/cart`, { headers })).json();
    assert.equal(cart.items[0].quantity, 2);
    await screenshot(page, `cart-filled`, true);
    console.log("PASS: guest and customer permissions, empty states, catalog and cart recovery");
    await compare(browser, token, cart);

    const paidId = await checkout(page, "pickup");
    await button(page, "Оплатить тестовым платежом").click();
    await heading(page, "Оплата заказа").waitFor();
    await screenshot(page, `payment-form`, true);
    await checkWidth(page, "test payment");
    await button(page, "Оплатить").click();
    await heading(page, "Результат: Оплачен").waitFor();
    await screenshot(page, `payment-success`, true);
    await link(page, "Вернуться к заказу").click();
    await page.locator(".status-pill--paid").waitFor();
    await page.goto(`${base}/account/orders`);
    await page.getByRole("link", { name: new RegExp(`Заказ №${paidId}`) }).waitFor();
    await checkWidth(page, "order history");
    await screenshot(page, `order-history`, true);
    await page.goto(`${base}/cart`);
    await heading(page, "Корзина пуста").waitFor();
    console.log(`PASS: browser purchase #${paidId}`);

    await page.setViewportSize({ width: 390, height: 844 });
    const readStock = async () => {
      const response = await page.request.get(`${base}/api/products/${product.id}`);
      return (await response.json()).variants.find(({ id }) => id === variant.id).stock;
    };
    const stockBefore = await readStock();
    await page.goto(`${base}/products/${product.id}`);
    await addVariant(page, product, variant);
    const pickupFailure = "**/api/pickup-points";
    await page.route(pickupFailure, (route) => route.fulfill({ status: 503, json: { detail: "Пункты недоступны" } }));
    const cancelledId = await checkout(page, "courier");
    await page.unroute(pickupFailure);
    assert.equal(await readStock(), stockBefore - 1);
    await button(page, "Отменить заказ").click();
    await page.locator(".status-pill--cancelled").waitFor();
    assert.equal(await button(page, "Оплатить тестовым платежом").count(), 0);
    assert.equal(await readStock(), stockBefore);
    await screenshot(page, "order-cancelled-mobile", true);

    await page.setViewportSize({ width: 768, height: 900 });
    await page.route("**/api/orders?*", (route) => route.abort(), { times: 1 });
    await page.goto(`${base}/account/orders`);
    await page.getByRole("alert").filter({ hasText: "Сервер недоступен" }).waitFor();
    await button(page, "Повторить").click();
    await page.getByRole("link", { name: new RegExp(`Заказ №${paidId}`) }).waitFor();
    await page.getByLabel("Статус").selectOption("cancelled");
    await page.getByRole("link", { name: new RegExp(`Заказ №${cancelledId}`) }).waitFor();
    await page.getByRole("link", { name: new RegExp(`Заказ №${paidId}`) }).waitFor({ state: "hidden" });
    await checkWidth(page, "order history tablet");
    assert.deepEqual(pageErrors, []);
    await checkAdmin(browser, paidId);
    console.log(JSON.stringify({ paidId, cancelledId, stockBefore, stockAfterCancellation: await readStock(), viewportWidths: [360, 390, 768], pageErrors }));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
