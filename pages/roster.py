import streamlit as st
import asyncio
import nest_asyncio
import pandas as pd
from playwright.async_api import async_playwright
from utils.data_processing import async_get_profiles_from_guild
from bs4 import BeautifulSoup
import os
os.system("playwright install")

# Патчим event loop для корректной работы асинхронного кода в Streamlit
nest_asyncio.apply()

async def async_get_profile_stats(context, profile_url: str) -> tuple:
    """
    Пытается открыть страницу профиля с показателями:
      • "Сила 11 лучших"
      • "Ср. сила 11 лучших"
    Делает до 3-х попыток навигации с таймаутом 30 секунд за попытку.
    Если ни одна попытка не успешна — возвращает ("N/A", "N/A").
    После успешного перехода ждет 3 секунды для загрузки динамики,
    затем извлекает значения через XPath-селекторы с ожиданием (до 15 сек).
    При необходимости используется fallback через BeautifulSoup.
    """
    max_retries = 3
    page_timeout = 30000  # таймаут в мс (30 сек)
    page = await context.new_page()
    navigation_success = False

    for attempt in range(max_retries):
        try:
            await page.goto(profile_url, timeout=page_timeout, wait_until="domcontentloaded")
            navigation_success = True
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} to navigate to {profile_url} failed: {e}")
            await asyncio.sleep(2)
    if not navigation_success:
        print(f"Navigation failed for {profile_url} after {max_retries} attempts. Returning N/A.")
        await page.close()
        return "N/A", "N/A"

    # Ждем, чтобы динамический контент подгрузился
    await asyncio.sleep(3)

    power_value = "N/A"
    avg_value = "N/A"

    # XPath-селекторы для нужных значений
    power_selector = "//td[contains(normalize-space(.), 'Сила 11 лучших')]/following-sibling::td[1]"
    avg_selector = "//td[contains(normalize-space(.), 'Ср. сила 11 лучших')]/following-sibling::td[1]"

    try:
        await page.wait_for_selector(power_selector, timeout=15000)
        power_element = await page.query_selector(power_selector)
        if power_element:
            power_value = (await power_element.inner_text()).strip()
    except Exception as e:
        print(f"Error retrieving 'Сила 11 лучших' for {profile_url}: {e}")

    try:
        await page.wait_for_selector(avg_selector, timeout=15000)
        avg_element = await page.query_selector(avg_selector)
        if avg_element:
            avg_value = (await avg_element.inner_text()).strip()
    except Exception as e:
        print(f"Error retrieving 'Ср. сила 11 лучших' for {profile_url}: {e}")

    # Если значения так и не получены, пробуем fallback через BeautifulSoup.
    if power_value == "N/A" or avg_value == "N/A":
        try:
            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            if power_value == "N/A":
                power_td = soup.find("td", text=lambda t: t and "Сила 11 лучших" in t)
                if power_td:
                    next_td = power_td.find_next_sibling("td")
                    if next_td:
                        power_value = next_td.get_text(strip=True)
            if avg_value == "N/A":
                avg_td = soup.find("td", text=lambda t: t and "Ср. сила 11 лучших" in t)
                if avg_td:
                    next_td = avg_td.find_next_sibling("td")
                    if next_td:
                        avg_value = next_td.get_text(strip=True)
        except Exception as e:
            print(f"Fallback error parsing HTML for {profile_url}: {e}")

    await page.close()
    return power_value, avg_value

async def async_get_roster(guild_url: str, login: str, password: str):
    """
    Логинится на сайте, переходит на страницу союза и получает:
      • Название союза (из элемента <h3>)
      • Список участников союза (функция async_get_profiles_from_guild возвращает кортежи (profile_url, nickname))
    Из списка исключается профиль, под которым выполнена авторизация.
    Для каждого участника параллельно вызывается async_get_profile_stats
    для получения:
      • "Сила 11 лучших"
      • "Ср. сила 11 лучших"
    Чтобы избежать перегрузок, используется asyncio.Semaphore для ограничения
    количества одновременно открытых страниц.
    Возвращает кортеж:
         (alliance_name, список кортежей (profile_url, nickname, power_value, avg_power_value))
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        # Авторизация
        await page.goto("https://11x11.ru/", timeout=30000, wait_until="domcontentloaded")
        await page.fill("input[name='auth_name']", login)
        await page.fill("input[name='auth_pass1']", password)
        await page.click("xpath=//input[@type='submit' and @value='Войти']")
        await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)

        # Получаем URL залогиненного профиля для фильтрации
        logged_profile_link = await page.query_selector("a[href^='/users/']")
        logged_profile_url = None
        if logged_profile_link:
            href = await logged_profile_link.get_attribute("href")
            if href and href.startswith("/users/"):
                logged_profile_url = "https://11x11.ru" + href

        # Переход на страницу союза для получения названия союза
        await page.goto(guild_url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        alliance_name = "N/A"
        try:
            alliance_name_el = await page.wait_for_selector("h3", timeout=15000)
            alliance_name = (await alliance_name_el.inner_text()).strip()
        except Exception as e:
            print(f"Error retrieving alliance name for {guild_url}: {e}")

        # Получаем список участников союза через функцию async_get_profiles_from_guild
        roster = await async_get_profiles_from_guild(page, guild_url)
        if logged_profile_url:
            roster = [entry for entry in roster if entry[0] != logged_profile_url]
        await page.close()

        # Ограничиваем количество одновременно запускаемых задач с помощью семафора
        semaphore = asyncio.Semaphore(20)

        async def safe_get_profile_stats(profile_url: str) -> tuple:
            async with semaphore:
                return await async_get_profile_stats(context, profile_url)

        tasks = []
        for profile in roster:
            profile_url, _ = profile
            tasks.append(safe_get_profile_stats(profile_url))
        stats_values = await asyncio.gather(*tasks)

        new_roster = []
        for (profile_url, nickname), (power, avg_power) in zip(roster, stats_values):
            new_roster.append((profile_url, nickname, power, avg_power))

        await context.close()
        await browser.close()
        return alliance_name, new_roster

def roster_page():
    st.title("Ростер игроков")
    guild_url = st.text_input("Введите URL союза:", value="https://11x11.ru/guilds/139")
    login = "лао"
    password = "111333555"

    if st.button("Получить ростер"):
        with st.spinner("Загружаем ростер игроков..."):
            try:
                loop = asyncio.get_event_loop()
                alliance_name, roster = loop.run_until_complete(async_get_roster(guild_url, login, password))
            except Exception as e:
                st.error(f"Ошибка: {e}")
                return

        st.markdown(f"### Союз: {alliance_name}")
        if roster:
            st.markdown("### Список участников:")
            data = []
            for profile_url, nickname, power, avg_power in roster:
                data.append({
                    "Профиль": f'<a href="{profile_url}" target="_blank">{nickname}</a>',
                    "Сила 11 лучших": power,
                    "Ср. сила 11 лучших": avg_power
                })
            df = pd.DataFrame(data)
            st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.write("Нет результатов.")

if __name__ == "__main__":
    roster_page()
