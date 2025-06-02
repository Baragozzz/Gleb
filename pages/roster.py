import streamlit as st
import asyncio
from playwright.async_api import async_playwright
from utils.data_processing import async_get_profiles_from_guild  # Импортирование функции сбора участников

async def async_get_roster(guild_url: str, login: str, password: str):
    """Асинхронно авторизуется и получает ростер участников союза по URL."""
    async with async_playwright() as p:
        # Запускаем браузер с отключённым sandbox для совместимости
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()
        
        # Авторизация:
        await page.goto("https://11x11.ru/", timeout=15000, wait_until="domcontentloaded")
        await page.fill("input[name='auth_name']", login)
        await page.fill("input[name='auth_pass1']", password)
        await page.click("xpath=//input[@type='submit' and @value='Войти']")
        await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)
        
        # Получаем список профилей союза
        roster = await async_get_profiles_from_guild(page, guild_url)
        
        # Закрываем ресурсы
        await page.close()
        await context.close()
        await browser.close()
        
        return roster

def roster_page():
    """Страница для вывода списка участников (ростера) союза."""
    st.subheader("Ростер игроков")
    
    # Ввод URL союза (например, https://11x11.ru/guilds/139)
    guild_url = st.text_input("Введите URL союза:", value="https://11x11.ru/guilds/139")
    
    # Данные для авторизации (здесь не меняем их)
    login = "лао"
    password = "111333555"
    
    if st.button("Получить ростер"):
        st.write("Загружаем ростер игроков...")
        try:
            roster = asyncio.run(async_get_roster(guild_url, login, password))
        except Exception as e:
            st.error(f"Произошла ошибка: {e}")
            return
        
        if roster:
            st.write("Список участников:")
            # roster — это список кортежей (profile_url, nickname)
            for profile in roster:
                profile_url, nickname = profile
                st.markdown(f"* <a href='{profile_url}' target='_blank'>{nickname}</a>", unsafe_allow_html=True)
        else:
            st.write("Не удалось получить список участников.")

if __name__ == "__main__":
    roster_page()
