import streamlit as st
import subprocess
import re
import pandas as pd
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError

# Попытка динамически установить Chromium (если ещё не установлен)
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    st.write("Ошибка установки playwright chromium:", e)

def parse_date(date_str):
    """Преобразует строку с датой формата 'ДД.ММ.ГГГГ ЧЧ:ММ' в объект datetime."""
    return datetime.strptime(date_str, "%d.%m.%Y %H:%M")

def clean_nickname(raw_text):
    """
    Очищает текст никнейма.
    Например, из строки "Профиль участника Мечтатель – Онлайн игра 11x11" возвращается "Мечтатель".
    """
    nickname = raw_text.strip()
    if "Профиль участника" in nickname:
        nickname = nickname.replace("Профиль участника", "").strip()
    if "–" in nickname:
        nickname = nickname.split("–")[0].strip()
    elif "-" in nickname:
        nickname = nickname.split("-")[0].strip()
    return nickname

async def async_get_nickname(page, profile_url):
    """
    Асинхронно переходит на страницу профиля и пытается извлечь никнейм.
    Сначала используется содержимое тега <title>, затем <h1>.
    Если загрузка не успешна (таймаут), возвращается последний компонент URL.
    """
    try:
        await page.goto(profile_url, timeout=15000, wait_until="domcontentloaded")
    except TimeoutError:
        return profile_url.split("/")[-1]
    except Exception:
        return profile_url.split("/")[-1]
    
    try:
        await page.wait_for_selector("h1", timeout=10000)
    except Exception:
        pass

    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text()
        nickname = clean_nickname(title_text)
        if nickname:
            return nickname
    h1 = soup.find("h1")
    if h1:
        nickname = clean_nickname(h1.get_text())
        if nickname:
            return nickname
    return profile_url.split("/")[-1]

async def async_collect_stats_for_profile(page, profile_url, filter_from, filter_to, computed_stats):
    """
    Асинхронно собирает статистику для профиля (победы, ничьи, поражения).
    Если статистика уже посчитана (по user_id), используется кэш.
    """
    user_id_match = re.search(r'/users/(\d+)', profile_url)
    if not user_id_match:
        return (0, 0, 0)
    user_id = user_id_match.group(1)
    if user_id in computed_stats:
        return computed_stats[user_id]
    
    wins = draws = losses = 0
    page_num = 1
    while True:
        history_url = (
            f"https://11x11.ru/xml/games/history.php?page={page_num}"
            f"&type=games/history&act=userhistory&user={user_id}"
        )
        try:
            await page.goto(history_url, timeout=15000, wait_until="domcontentloaded")
        except Exception:
            break
        try:
            await page.wait_for_selector("tr", timeout=10000)
        except Exception:
            pass
        
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr")
        if not rows:
            break
        found_match = False
        stop = False
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            date_str = cols[0].get_text().strip()
            if not date_str:
                continue
            try:
                dt = parse_date(date_str)
            except Exception:
                continue
            if dt < filter_from:
                stop = True
                break
            if dt > filter_to:
                continue
            found_match = True
            center = cols[2]
            result = "Draw"
            b_tag = center.find("b")
            if b_tag and b_tag.find("a"):
                href = b_tag.find("a")["href"]
                if user_id in href:
                    result = "Win"
                else:
                    result = "Loss"
            if result == "Win":
                wins += 1
            elif result == "Loss":
                losses += 1
            else:
                draws += 1
        if stop or not found_match:
            break
        page_num += 1
    computed_stats[user_id] = (wins, draws, losses)
    return wins, draws, losses

async def async_get_profiles_from_guild(page, guild_url):
    """
    Асинхронно получает список участников союза.
    Для каждого найденного профиля возвращается кортеж (profile_url, nickname).
    Цикл завершается, если на следующей странице не появляется ни одного нового уникального элемента.
    """
    guild_id_match = re.search(r'/guilds/(\d+)', guild_url)
    if not guild_id_match:
        return []
    guild_id = guild_id_match.group(1)
    profiles = set()
    pagenum = 1
    while True:
        members_url = (
            f"https://11x11.ru/xml/misc/guilds.php?page={pagenum}"
            f"&type=misc/guilds&act=members&id={guild_id}"
        )
        try:
            await page.goto(members_url, timeout=15000, wait_until="domcontentloaded")
        except Exception:
            break
        try:
            await page.wait_for_selector("a[href^='/users/']", timeout=10000)
        except Exception:
            pass
        
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        new_profiles = set()
        for a in soup.find_all("a", href=True):
            if re.match(r"^/users/\d+", a["href"]):
                profile_url = "https://11x11.ru" + a["href"]
                nickname = clean_nickname(a.get_text(strip=True))
                if not nickname:
                    nickname = profile_url.split("/")[-1]
                new_profiles.add((profile_url, nickname))
        diff = new_profiles - profiles
        if not diff:
            break
        profiles.update(diff)
        pagenum += 1
    return list(profiles)

async def process_profile(context, profile_url, filter_from, filter_to, computed_stats):
    """
    Создаёт новую вкладку для профиля, получает ник и статистику,
    затем закрывает вкладку. Возвращает кортеж (profile_url, nickname, wins, draws, losses).
    """
    page = await context.new_page()
    nickname = await async_get_nickname(page, profile_url)
    wins, draws, losses = await async_collect_stats_for_profile(page, profile_url, filter_from, filter_to, computed_stats)
    await page.close()
    return profile_url, nickname, wins, draws, losses

async def async_main(mode_choice, target_url, filter_from, filter_to, login, password):
    computed_stats = {}
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        # Страница для авторизации (и получения списка участников, если режим "Союз")
        page = await context.new_page()
        try:
            await page.goto("https://11x11.ru/", timeout=15000, wait_until="domcontentloaded")
        except Exception:
            st.write("Ошибка загрузки главной страницы")
            return []
        await page.fill("input[name='auth_name']", login)
        await page.fill("input[name='auth_pass1']", password)
        await page.click("xpath=//input[@type='submit' and @value='Войти']")
        try:
            await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)
        except Exception:
            st.write("Ошибка авторизации или загрузки страницы после входа")
            return []
        
        if mode_choice == "Профилю":
            # Режим одиночного профиля – обрабатываем один профиль
            profile_url, nickname, wins, draws, losses = await process_profile(context, target_url, filter_from, filter_to, computed_stats)
            results.append({
                "Профиль": f'<a href="{profile_url}" target="_blank">{nickname}</a>',
                "Побед": wins,
                "Ничьих": draws,
                "Поражений": losses
            })
        else:
            # Режим "Союз" – получаем список участников
            profile_tuples = await async_get_profiles_from_guild(page, target_url)
            if not profile_tuples:
                await page.close()
                await context.close()
                await browser.close()
                return []
            semaphore = asyncio.Semaphore(10)
            async def sem_process(profile_url):
                async with semaphore:
                    return await process_profile(context, profile_url, filter_from, filter_to, computed_stats)
            tasks = [sem_process(profile_url) for (profile_url, _) in profile_tuples]
            profiles_results = await asyncio.gather(*tasks)
            # Фильтрация и дедупликация по user_id; пропускаем записи с ником "Профиль"
            dedup = {}
            for pr in profiles_results:
                profile_url, nickname, wins, draws, losses = pr
                match = re.search(r'/users/(\d+)', profile_url)
                if not match:
                    continue
                user_id = match.group(1)
                if nickname == "Профиль":
                    continue
                dedup[user_id] = (profile_url, nickname, wins, draws, losses)
            profiles_results = list(dedup.values())
            
            total_players = len(profiles_results)
            active_count = sum(1 for (_, _, w, d, l) in profiles_results if (w + d + l) > 0)
            inactive_count = total_players - active_count
            
            for (profile_url, nickname, wins, draws, losses) in profiles_results:
                results.append({
                    "Профиль": f'<a href="{profile_url}" target="_blank">{nickname}</a>',
                    "Побед": wins,
                    "Ничьих": draws,
                    "Поражений": losses
                })
            summary = f"Всего игроков: {total_players}, из них играли: {active_count}, из них не играли: {inactive_count}"
            results.append({
                "Профиль": f"<b>{summary}</b>",
                "Побед": "",
                "Ничьих": "",
                "Поражений": ""
            })
            await page.close()
        await context.close()
        await browser.close()
    return results

def main():
    st.title("11x11 Статистика")
    st.write("Приложение запустилось!")
    
    mode_choice = st.selectbox("Строить статистику по:", ("Профилю", "Союзу"))
    period_mode = st.selectbox("Режим периода", ("День", "Интервал"))
    
    if period_mode == "День":
        day = st.text_input("Дата (ДД.ММ):", value=datetime.now().strftime("%d.%m"))
        year = datetime.now().year
        filter_from = datetime.strptime(f"{day}.{year} 00:00", "%d.%m.%Y %H:%M")
        filter_to = datetime.strptime(f"{day}.{year} 23:59", "%d.%m.%Y %H:%M")
    else:
        dt_from = st.text_input("От (ДД.ММ.ГГГГ ЧЧ:ММ):", value="01.01.2021 00:00")
        dt_to = st.text_input("До (ДД.ММ.ГГГГ ЧЧ:ММ):", value="31.12.2021 23:59")
        filter_from = datetime.strptime(dt_from, "%d.%m.%Y %H:%M")
        filter_to = datetime.strptime(dt_to, "%d.%m.%Y %H:%M")
        
    if mode_choice == "Профилю":
        target_url = st.text_input("Введите URL профиля:", value="https://11x11.ru/users/3941656")
    else:
        target_url = st.text_input("Введите URL союза:", value="https://11x11.ru/guilds/139")
    
    if st.button("Собрать статистику"):
        login = "лао"
        password = "111333555"
        results = asyncio.run(async_main(mode_choice, target_url, filter_from, filter_to, login, password))
        if results:
            df = pd.DataFrame(results)
            st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.write("Нет результатов.")

if __name__ == "__main__":
    main()
