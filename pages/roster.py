import streamlit as st
import asyncio
import nest_asyncio
import pandas as pd
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from utils.data_processing import async_get_profiles_from_guild

# Патчим event loop для корректной работы асинхронного кода в Streamlit
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
        # Добавляем небольшую задержку, чтобы динамический контент успел загрузиться
        await asyncio.sleep(1)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        power_value = "N/A"
        avg_power_value = "N/A"
        
        # Поиск "Сила 11 лучших"
        power_label_td = soup.find("td", string=re.compile(r"Сила\s*11\s*лучших", re.IGNORECASE))
        if power_label_td:
            next_td = power_label_td.find_next_sibling("td")
            if next_td:
                power_value = next_td.get_text(strip=True)
        
        # Поиск "Ср. сила 11 лучших"
        avg_power_label_td = soup.find("td", string=re.compile(r"Ср\.\s*сила\s*11\s*лучших", re.IGNORECASE))
        if avg_power_label_td:
            next_avg_td = avg_power_label_td.find_next_sibling("td")
            if next_avg_td:
                avg_power_value = next_avg_td.get_text(strip=True)
                
        return power_value, avg_power_value
    except Exception as e:
        print(f"Error in async_get_profile_stats for {profile_url}: {e}")
        return "N/A", "N/A"
    finally:
        await page.close()

async def async_get_roster(guild_url: str, login: str, password: str):
    """
    Авторизуется на сайте, получает список участников союза и для каждого профиля извлекает показатели:
      - "Сила 11 лучших"
      - "Ср. сила 11 лучших"
    Возвращает список кортежей (profile_url, nickname, power_value, avg_power_value).
    При этом из списка автоматически исключается профиль, под которым мы логинимся.
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
        
        # Получаем ссылку залогиненного пользователя
        logged_profile_link = await page.query_selector("a[href^='/users/']")
        logged_profile_url = None
        if logged_profile_link:
            href = await logged_profile_link.get_attribute("href")
            if href and href.startswith("/users/"):
                logged_profile_url = "https://11x11.ru" + href
        
        # Получаем список участников союза – кортежи (profile_url, nickname)
        roster = await async_get_profiles_from_guild(page, guild_url)
        # Фильтруем: исключаем профиль залогиненного пользователя, если он есть в списке
        if logged_profile_url:
            roster = [entry for entry in roster if entry[0] != logged_profile_url]
        
        await page.close()
        
        # Для каждого профиля получаем показатели "Сила 11 лучших" и "Ср. сила 11 лучших"
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
