import streamlit as st
import asyncio
import nest_asyncio
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from utils.data_processing import async_get_profiles_from_guild

# Патчим event loop, чтобы работать в Streamlit
nest_asyncio.apply()

async def async_get_profile_power(context, profile_url: str) -> str:
    """
    Открывает страницу профиля и извлекает значение "Сила 11 лучших".
    Ищет ячейку с текстом "Сила 11 лучших" и возвращает текст следующей ячейки.
    """
    page = await context.new_page()
    try:
        await page.goto(profile_url, timeout=15000, wait_until="domcontentloaded")
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        # Ищем <td>, содержащий текст "Сила 11 лучших"
        label_td = soup.find("td", string=lambda text: text and "Сила 11 лучших" in text)
        if label_td:
            next_td = label_td.find_next_sibling("td")
            if next_td:
                return next_td.get_text(strip=True)
        return "N/A"
    except Exception:
        return "N/A"
    finally:
        await page.close()

async def async_get_roster(guild_url: str, login: str, password: str):
    """
    Авторизуется, получает список участников союза и для каждого профиля извлекает "Сила 11 лучших".
    Возвращает список кортежей (profile_url, nickname, сила_11_лучших).
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
        
        # Получаем список участников союза — список кортежей (profile_url, nickname)
        roster = await async_get_profiles_from_guild(page, guild_url)
        await page.close()  # закрываем страницу авторизации, дальнейшие запросы будем делать через context
        
        # Для каждого профиля получаем силу 11 лучших
        tasks = []
        for profile in roster:
            profile_url, _ = profile
            tasks.append(async_get_profile_power(context, profile_url))
        power_values = await asyncio.gather(*tasks)
        
        new_roster = []
        for (profile_url, nickname), power in zip(roster, power_values):
            new_roster.append((profile_url, nickname, power))
        
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
        st.write("Загружаем ростер игроков...")
        try:
            # Запускаем асинхронное выполнение с использованием уже запатченного loop
            loop = asyncio.get_event_loop()
            roster = loop.run_until_complete(async_get_roster(guild_url, login, password))
        except Exception as e:
            st.error(f"Ошибка: {e}")
            return
        
        if roster:
            st.markdown("### Список участников:")
            data = []
            for profile_url, nickname, power in roster:
                data.append({
                    "Профиль": f'<a href="{profile_url}" target="_blank">{nickname}</a>',
                    "Сила 11 лучших": power
                })
            df = pd.DataFrame(data)
            st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.write("Нет результатов.")

if __name__ == "__main__":
    roster_page()
