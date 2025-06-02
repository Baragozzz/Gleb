import streamlit as st
import asyncio
import nest_asyncio
import pandas as pd
from playwright.async_api import async_playwright
from utils.data_processing import async_get_profiles_from_guild

# Патчим event loop для корректной работы асинхронного кода в Streamlit
nest_asyncio.apply()

async def async_get_profile_stats(context, profile_url: str) -> tuple:
    """
    Открывает страницу профиля и извлекает показатели:
      • "Сила 11 лучших"
      • "Ср. сила 11 лучших"
    Если переход на страницу не удаётся выполнить за 15 секунд, или значения не получены – функция сразу возвращает "N/A".
    """
    page = await context.new_page()
    try:
        # Пытаемся перейти на страницу профиля с таймаутом 15 сек.
        try:
            await page.goto(profile_url, timeout=15000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"Navigation error for {profile_url}: {e}. Skipping profile.")
            return "N/A", "N/A"

        # Ждем короткую задержку для динамического контента
        await asyncio.sleep(3)

        # Извлекаем значение "Сила 11 лучших"
        try:
            power_selector = "//td[contains(normalize-space(.), 'Сила 11 лучших')]/following-sibling::td[1]"
            await page.wait_for_selector(power_selector, timeout=10000)
            power_element = await page.query_selector(power_selector)
            power_value = (await power_element.inner_text()).strip() if power_element else "N/A"
        except Exception as e:
            print(f"Error retrieving 'Сила 11 лучших' for {profile_url}: {e}")
            power_value = "N/A"

        # Извлекаем значение "Ср. сила 11 лучших"
        try:
            avg_selector = "//td[contains(normalize-space(.), 'Ср. сила 11 лучших')]/following-sibling::td[1]"
            await page.wait_for_selector(avg_selector, timeout=10000)
            avg_element = await page.query_selector(avg_selector)
            avg_value = (await avg_element.inner_text()).strip() if avg_element else "N/A"
        except Exception as e:
            print(f"Error retrieving 'Ср. сила 11 лучших' for {profile_url}: {e}")
            avg_value = "N/A"

        return power_value, avg_value

    except Exception as e:
        print(f"General error in async_get_profile_stats for {profile_url}: {e}")
        return "N/A", "N/A"
    finally:
        await page.close()

async def async_get_roster(guild_url: str, login: str, password: str):
    """
    Авторизуется на сайте, переходит на страницу союза, получает название союза и список участников.
    Для каждого участника (за исключением профиля, под которым выполнена авторизация) с помощью async_get_profile_stats
    извлекаются показатели "Сила 11 лучших" и "Ср. сила 11 лучших".
    Возвращает кортеж:
         (alliance_name, список кортежей (profile_url, nickname, power_value, avg_power_value))
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()

        # Авторизация
        await page.goto("https://11x11.ru/", timeout=30000, wait_until="domcontentloaded")
        await page.fill("input[name='auth_name']", login)
        await page.fill("input[name='auth_pass1']", password)
        await page.click("xpath=//input[@type='submit' and @value='Войти']")
        await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)

        # Получаем URL залогиненного профиля, чтобы затем исключить его из списка
        logged_profile_link = await page.query_selector("a[href^='/users/']")
        logged_profile_url = None
        if logged_profile_link:
            href = await logged_profile_link.get_attribute("href")
            if href and href.startswith("/users/"):
                logged_profile_url = "https://11x11.ru" + href

        # Переход на страницу союза для получения названия альянса
        await page.goto(guild_url, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        alliance_name = "N/A"
        try:
            alliance_name_el = await page.wait_for_selector("h3", timeout=15000)
            alliance_name = (await alliance_name_el.inner_text()).strip()
        except Exception as e:
            print(f"Error retrieving alliance name for {guild_url}: {e}")

        # Получаем список участников союза (функция async_get_profiles_from_guild должна возвращать кортежи (profile_url, nickname))
        roster = await async_get_profiles_from_guild(page, guild_url)
        if logged_profile_url:
            roster = [entry for entry in roster if entry[0] != logged_profile_url]
        await page.close()

        # Для каждого участника извлекаем показатели
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
