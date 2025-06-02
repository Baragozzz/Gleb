import streamlit as st
import asyncio
import nest_asyncio
import pandas as pd
import re
from playwright.async_api import async_playwright
from utils.data_processing import async_get_profiles_from_guild

# Патчим event loop для корректной работы асинхронного кода в Streamlit
nest_asyncio.apply()

async def async_get_profile_stats(context, profile_url: str) -> tuple:
    """
    Открывает страницу профиля и пытается извлечь показатели:
      • "Сила 11 лучших"
      • "Ср. сила 11 лучших"
    Производит до 3-х попыток с ожиданием селектора для повышения стабильности.
    Использует Playwright-селекторы для прямого взаимодействия с DOM.
    Возвращает кортеж (power_value, avg_power_value).
    """
    page = await context.new_page()
    try:
        # Ждем, пока страница загрузится до состояния networkidle
        await page.goto(profile_url, timeout=15000, wait_until="networkidle")
        max_attempts = 3
        power_value = "N/A"
        avg_power_value = "N/A"
        selector_power = "xpath=//td[contains(text(), 'Сила 11 лучших')]/following-sibling::td"
        selector_avg   = "xpath=//td[contains(text(), 'Ср. сила 11 лучших')]/following-sibling::td"
        for attempt in range(max_attempts):
            try:
                await page.wait_for_selector(selector_power, timeout=5000)
                element_power = await page.query_selector(selector_power)
                if element_power:
                    new_power = (await element_power.inner_text()).strip()
                    if new_power:
                        power_value = new_power
            except Exception:
                pass

            try:
                await page.wait_for_selector(selector_avg, timeout=5000)
                element_avg = await page.query_selector(selector_avg)
                if element_avg:
                    new_avg = (await element_avg.inner_text()).strip()
                    if new_avg:
                        avg_power_value = new_avg
            except Exception:
                pass

            # Если хотя бы одно значение получено – завершаем цикл попыток
            if power_value != "N/A" or avg_power_value != "N/A":
                break
            await asyncio.sleep(1)
        return power_value, avg_power_value
    except Exception as e:
        print(f"Error in async_get_profile_stats for {profile_url}: {e}")
        return "N/A", "N/A"
    finally:
        await page.close()

async def async_get_roster(guild_url: str, login: str, password: str):
    """
    Логинится на сайте, переходит на страницу союза, пытается получить название союза и список его участников.
    Для каждого профиля (кроме профиля, под которым залогинены) с помощью async_get_profile_stats
    извлекаются показатели "Сила 11 лучших" и "Ср. сила 11 лучших".
    Возвращает кортеж:
         (alliance_name, список кортежей (profile_url, nickname, power_value, avg_power_value)).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        # Авторизация
        await page.goto("https://11x11.ru/", timeout=15000, wait_until="networkidle")
        await page.fill("input[name='auth_name']", login)
        await page.fill("input[name='auth_pass1']", password)
        await page.click("xpath=//input[@type='submit' and @value='Войти']")
        await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)

        # Получим URL залогиненного профиля
        logged_profile_link = await page.query_selector("a[href^='/users/']")
        logged_profile_url = None
        if logged_profile_link:
            href = await logged_profile_link.get_attribute("href")
            if href and href.startswith("/users/"):
                logged_profile_url = "https://11x11.ru" + href

        # Переход на страницу союза
        await page.goto(guild_url, timeout=15000, wait_until="networkidle")
        alliance_name = "N/A"
        try:
            # Ждем появления <h3> с названием союза
            await page.wait_for_selector("xpath=//h3", timeout=10000)
            alliance_name_el = await page.query_selector("xpath=//h3")
            if alliance_name_el:
                alliance_name = (await alliance_name_el.inner_text()).strip()
        except Exception as e:
            print("Error getting alliance name:", e)

        # Получаем список участников союза
        roster = await async_get_profiles_from_guild(page, guild_url)
        if logged_profile_url:
            roster = [entry for entry in roster if entry[0] != logged_profile_url]
        await page.close()

        # Для каждого профиля получаем показатели
        tasks = []
        for profile in roster:
            profile_url, _ = profile
            tasks.append(async_get_profile_stats(context, profile_url))
        stats_values = await asyncio.gather(*tasks)

        new_roster = []
        for (profile_url, nickname), (power, avg_power) in zip(roster, stats_values):
            new_roster.append((profile_url, nickname, power, avg_power))
        await context.close()
        await browser.close()
        return alliance_name, new_roster

def roster_page():
    st.title("Ростер игроков")
    # Ввод URL союза
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
