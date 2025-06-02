import streamlit as st
import asyncio
import nest_asyncio
import pandas as pd
import re
from playwright.async_api import async_playwright
from utils.data_processing import async_get_profiles_from_guild
from bs4 import BeautifulSoup
import os
os.system("playwright install")

# Патчим event loop для корректной работы асинхронного кода в Streamlit
nest_asyncio.apply()

async def async_get_profile_stats(context, profile_url: str) -> tuple:
    """
    Открывает страницу профиля и извлекает:
      - "Сила 11 лучших"
      - "Gk": максимальное значение из колонки "Мас" для игроков, 
         у которых в колонке "Поз" равно "Gk". При обходе таблицы игроков 
         итерация прекращается при встрече строки с иным значением в "Поз".

    Если хотя бы один показатель равен "N/A", функция повторяет всю процедуру до 5 раз.
    Возвращает кортеж (power_value, gk_value).
    """
    max_outer_attempts = 5
    final_result = ("N/A", "N/A")
    for outer_attempt in range(max_outer_attempts):
        page = await context.new_page()
        try:
            # Внутренний цикл (до 3-х попыток навигации)
            max_inner_attempts = 3
            navigation_success = False
            for inner in range(max_inner_attempts):
                try:
                    await page.goto(profile_url, timeout=15000, wait_until="domcontentloaded")
                    navigation_success = True
                    break
                except Exception as e:
                    print(f"Attempt {inner+1} to navigate to {profile_url} failed: {e}")
                    await asyncio.sleep(1)
            if not navigation_success:
                final_result = ("N/A", "N/A")
            else:
                await asyncio.sleep(1)  # время для загрузки динамического контента
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                
                # Извлечение "Сила 11 лучших"
                power_value = "N/A"
                power_label_td = soup.find("td", string=re.compile(r"Сила\s*11\s*лучших", re.IGNORECASE))
                if power_label_td:
                    next_td = power_label_td.find_next_sibling("td")
                    if next_td:
                        power_value = next_td.get_text(strip=True)
                        
                # Извлечение показателя "Gk"
                gk_value = "N/A"
                try:
                    players_table = None
                    # Сначала ищем заголовок h3 с текстом "Игроки команды"
                    h3_elem = soup.find("h3", string=re.compile(r"Игроки\s+команды", re.IGNORECASE))
                    if h3_elem:
                        players_table = h3_elem.find_next("table")
                    # Если через h3 не найдено, перебираем все таблицы на предмет наличия "Поз" и "Мас"
                    if not players_table:
                        for table in soup.find_all("table"):
                            header = table.find("tr")
                            if header:
                                header_text = header.get_text()
                                if "Поз" in header_text and "Мас" in header_text:
                                    players_table = table
                                    break
                    if players_table:
                        # Определяем индексы колонок "Поз" и "Мас" (ищем по наличию подстроки, без учета регистра)
                        header_cells = players_table.find("tr").find_all(["th", "td"])
                        poz_index = None
                        mas_index = None
                        for i, cell in enumerate(header_cells):
                            text = cell.get_text(strip=True).lower()
                            if "поз" in text:
                                poz_index = i
                            if "мас" in text:
                                mas_index = i
                        if poz_index is not None and mas_index is not None:
                            gk_masses = []
                            rows = players_table.find_all("tr")[1:]  # пропускаем заголовок
                            for row in rows:
                                cells = row.find_all("td")
                                if len(cells) > max(poz_index, mas_index):
                                    poz_text = cells[poz_index].get_text(strip=True).lower()
                                    # Если значение в "Поз" не равно "gk", прекращаем поиск
                                    if poz_text != "gk":
                                        break
                                    mas_text = cells[mas_index].get_text(strip=True)
                                    try:
                                        mass_val = float(mas_text)
                                    except:
                                        mass_val = None
                                    if mass_val is not None:
                                        gk_masses.append(mass_val)
                            if gk_masses:
                                gk_value = str(max(gk_masses))
                except Exception as e:
                    print(f"Error extracting GK value for {profile_url}: {e}")
                
                final_result = (power_value, gk_value)
        except Exception as ex:
            print(f"General error in async_get_profile_stats for {profile_url}: {ex}")
            final_result = ("N/A", "N/A")
        finally:
            await page.close()
            
        if final_result[0] != "N/A" and final_result[1] != "N/A":
            return final_result
        else:
            print(f"Outer attempt {outer_attempt+1} for {profile_url} resulted in {final_result}. Retrying...")
            await asyncio.sleep(1)
    return final_result

async def async_get_roster(guild_url: str, login: str, password: str):
    """
    Логинится на сайте, переходит на страницу союза и получает:
      - Название союза (из элемента <h3>)
      - Список участников союза (функция async_get_profiles_from_guild возвращает кортежи (profile_url, nickname))
    Из списка исключается профиль, под которым выполнена авторизация.
    Для каждого участника параллельно вызывается async_get_profile_stats для получения:
      - "Сила 11 лучших"
      - "Gk"
    Используется asyncio.Semaphore для ограничения количества одновременно открытых страниц.
    Возвращает кортеж:
         (alliance_name, список кортежей (profile_url, nickname, power_value, gk_value))
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
        
        # Получаем URL залогиненного профиля для исключения
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
        
        # Получаем список участников союза через async_get_profiles_from_guild
        roster = await async_get_profiles_from_guild(page, guild_url)
        if logged_profile_url:
            roster = [entry for entry in roster if entry[0] != logged_profile_url]
        await page.close()
        
        # Ограничиваем количество одновременно работающих задач с помощью семафора (лимит 20)
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
        for (profile_url, nickname), (power, gk) in zip(roster, stats_values):
            new_roster.append((profile_url, nickname, power, gk))
        
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
            for profile_url, nickname, power, gk in roster:
                data.append({
                    "Профиль": f'<a href="{profile_url}" target="_blank">{nickname}</a>',
                    "Сила 11 лучших": power,
                    "Gk": gk
                })
            df = pd.DataFrame(data)
            # Фильтруем строки, где в колонке "Профиль" отсутствуют буквы или цифры.
            df = df[df["Профиль"].str.contains(r"[A-Za-zА-Яа-я0-9]", regex=True)]
            st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.write("Нет результатов.")


if __name__ == "__main__":
    roster_page()
