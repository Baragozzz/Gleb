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
    Открывает страницу профиля и пытается извлечь два значения:
      • "Сила 11 лучших"
      • "Ср. сила 11 лучших"
      
    Используются XPath-селекторы с достаточными таймаутами.
    Если элемент не появляется в течение указанного времени, возвращается "N/A".
    """
    page = await context.new_page()
    try:
        # Переходим на страницу профиля и ждём, пока сеть будет неактивна
        await page.goto(profile_url, timeout=20000, wait_until="networkidle")
        
        # Используем селекторы для извлечения значений
        try:
            # Селектор для "Сила 11 лучших"
            power_selector = "//td[contains(normalize-space(.), 'Сила 11 лучших')]/following-sibling::td[1]"
            power_element = await page.wait_for_selector(power_selector, timeout=12000)
            power_value = (await power_element.inner_text()).strip()
        except Exception as e:
            print(f"Error retrieving 'Сила 11 лучших' for {profile_url}: {e}")
            power_value = "N/A"
            
        try:
            # Селектор для "Ср. сила 11 лучших"
            avg_selector = "//td[contains(normalize-space(.), 'Ср. сила 11 лучших')]/following-sibling::td[1]"
            avg_element = await page.wait_for_selector(avg_selector, timeout=12000)
            avg_value = (await avg_element.inner_text()).strip()
        except Exception as e:
            print(f"Error retrieving 'Ср. сила 11 лучших' for {profile_url}: {e}")
            avg_value = "N/A"
            
        return power_value, avg_value
        
    except Exception as e:
        print(f"Navigation error for {profile_url}: {e}")
        return "N/A", "N/A"
    finally:
        await page.close()

async def async_get_roster(guild_url: str, login: str, password: str):
    """
    Авторизуется на сайте, переходит на страницу союза, получает название союза и список участников.
    Для каждого участника извлекает с помощью async_get_profile_stats показатели:
      • "Сила 11 лучших"
      • "Ср. сила 11 лучших"
      
    При этом из списка исключается профиль, под которым происходит авторизация.
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

        # Авторизация на сайте
        await page.goto("https://11x11.ru/", timeout=20000, wait_until="networkidle")
        await page.fill("input[name='auth_name']", login)
        await page.fill("input[name='auth_pass1']", password)
        await page.click("xpath=//input[@type='submit' and @value='Войти']")
        await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)

        # Получаем URL залогиненного профиля (чтобы потом отфильтровать его)
        logged_profile_link = await page.query_selector("a[href^='/users/']")
        logged_profile_url = None
        if logged_profile_link:
            href = await logged_profile_link.get_attribute("href")
            if href and href.startswith("/users/"):
                logged_profile_url = "https://11x11.ru" + href

        # Переход на страницу союза для получения информации об альянсе
        await page.goto(guild_url, timeout=20000, wait_until="networkidle")
        alliance_name = "N/A"
        try:
            alliance_name_el = await page.wait_for_selector("h3", timeout=15000)
            alliance_name = (await alliance_name_el.inner_text()).strip()
        except Exception as e:
            print("Error retrieving alliance name via selector:", e)
            alliance_name = "N/A"

        # Получаем список участников союза (предполагается, что функция async_get_profiles_from_guild возвращает кортежи (profile_url, nickname))
        roster = await async_get_profiles_from_guild(page, guild_url)
        if logged_profile_url:
            roster = [entry for entry in roster if entry[0] != logged_profile_url]
        await page.close()

        # Для каждого участника извлекаем показатели, используя параллельный запуск
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
    # Ввод URL союза (по умолчанию, например, для союза с id=139)
    guild_url = st.text_input("Введите URL союза:", value="https://11x11.ru/guilds/139")
    # Фиксированные данные авторизации
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
