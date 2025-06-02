import streamlit as st
import asyncio
import nest_asyncio
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from utils.data_processing import async_get_profiles_from_guild

# Патчим event loop для работы в Streamlit
nest_asyncio.apply()

async def async_get_profile_stats(context, profile_url: str) -> tuple:
    """
    Открывает страницу профиля и извлекает:
    - Значение "Сила 11 лучших"
    - Значение "Ср. сила 11 лучших"
    Возвращает кортеж (power_value, avg_power_value).
    """
    page = await context.new_page()
    try:
        await page.goto(profile_url, timeout=15000, wait_until="domcontentloaded")
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        # Извлечение "Сила 11 лучших"
        power_value = "N/A"
        power_label_td = soup.find("td", string=lambda text: text and "Сила 11 лучших" in text)
        if power_label_td:
            next_td = power_label_td.find_next_sibling("td")
            if next_td:
                power_value = next_td.get_text(strip=True)
        
        # Извлечение "Ср. сила 11 лучших"
        avg_power_value = "N/A"
        avg_power_label_td = soup.find("td", string=lambda text: text and "Ср. сила 11 лучших" in text)
        if avg_power_label_td:
            next_avg_td = avg_power_label_td.find_next_sibling("td")
            if next_avg_td:
                avg_power_value = next_avg_td.get_text(strip=True)
                
        return power_value, avg_power_value
    except Exception:
        return "N/A", "N/A"
    finally:
        await page.close()

async def async_get_roster(guild_url: str, login: str, password: str):
    """
    Авторизуется, получает список участников союза и для каждого профиля извлекает
    показатели "Сила 11 лучших" и "Ср. сила 11 лучших".
    Возвращает список кортежей (profile_url, nickname, power_value, avg_power_value).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        # Авторизация
        await page.goto("https://11x11.ru/", timeout=15000, wait_until="domcontentloaded")
        await page.fill("input[name='auth_name']", login)
        await page.fill("input[name='auth_pass1']", password)
        await page.click("xpath=//input[@type='submit' and @value='Войти']")
        await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)
        
        # Получаем список участников союза – список кортежей (profile_url, nickname)
        roster = await async_get_profiles_from_guild(page, guild_url)
        await page.close()  # закрываем страницу авторизации
        
        # Для каждого профиля получаем "Сила 11 лучших" и "Ср. сила 11 лучших"
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
        return new_roster

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
                roster = loop.run_until_complete(async_get_roster(guild_url, login, password))
            except Exception as e:
                st.error(f"Ошибка: {e}")
                return
        
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
