import streamlit as st
import asyncio
import nest_asyncio
from playwright.async_api import async_playwright
from utils.data_processing import async_get_profiles_from_guild
import os
os.system("playwright install")

# Применим патч для текущего event loop
nest_asyncio.apply()

async def async_get_roster(guild_url: str, login: str, password: str):
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
        
        # Получаем список участников союза
        roster = await async_get_profiles_from_guild(page, guild_url)
        
        await page.close()
        await context.close()
        await browser.close()
        return roster

def roster_page():
    st.header("Ростер игроков")
    guild_url = st.text_input("Введите URL союза:", value="https://11x11.ru/guilds/139")
    login = "лао"
    password = "111333555"

    if st.button("Получить ростер"):
        st.write("Загружаем ростер игроков...")
        try:
            # Вместо asyncio.run() используем существующий event loop
            loop = asyncio.get_event_loop()
            roster = loop.run_until_complete(async_get_roster(guild_url, login, password))
        except Exception as e:
            st.error(f"Ошибка: {e}")
            return

        if roster:
            st.markdown("### Список участников:")
            for profile_url, nickname in roster:
                st.markdown(f"* <a href='{profile_url}' target='_blank'>{nickname}</a>", unsafe_allow_html=True)
        else:
            st.write("Нет результатов.")

if __name__ == "__main__":
    roster_page()
