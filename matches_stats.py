import streamlit as st
import subprocess
import re
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Попытка динамически установить Chromium (если ещё не установлен)
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    st.write("Ошибка установки playwright chromium:", e)

def parse_date(date_str):
    return datetime.strptime(date_str, "%d.%m.%Y %H:%M")

def get_nickname(page, profile_url):
    """
    Переход на страницу профиля и извлечение никнейма.
    Если не удаётся найти никнейм в теге <h1>, то возвращается последний компонент URL.
    """
    page.goto(profile_url)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    html = page.content()
    soup = BeautifulSoup(html, "html.parser")
    # Попытка найти никнейм в <h1>
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    else:
        return profile_url.split("/")[-1]

def collect_stats_for_profile(page, profile_url, filter_from, filter_to, computed_stats):
    """
    Считывает статистику (победы, ничьи, поражения) для профиля по истории игр.
    Используется кэш computed_stats, чтобы избежать повторного подсчёта для одного и того же профиля.
    """
    user_id_match = re.search(r'/users/(\d+)', profile_url)
    if not user_id_match:
        st.write(f"Неверный URL профиля: {profile_url}")
        return (0, 0, 0)
    user_id = user_id_match.group(1)
    if user_id in computed_stats:
        return computed_stats[user_id]
    wins = draws = losses = 0
    page_num = 1
    while True:
        history_url = (f"https://11x11.ru/xml/games/history.php?page={page_num}"
                       f"&type=games/history&act=userhistory&user={user_id}")
        page.goto(history_url)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        html = page.content()
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

def get_profiles_from_guild(page, guild_url):
    """
    Получает список членов союза.
    Из каждого найденного элемента <a>, соответствующего пользователю, извлекается пара:
    (URL профиля, никнейм) – текст ссылки считается никнеймом.
    """
    guild_id_match = re.search(r'/guilds/(\d+)', guild_url)
    if not guild_id_match:
        st.write("Неверный URL союза.")
        return []
    guild_id = guild_id_match.group(1)
    profiles = set()
    pagenum = 1
    while True:
        members_url = (f"https://11x11.ru/xml/misc/guilds.php?page={pagenum}"
                       f"&type=misc/guilds&act=members&id={guild_id}")
        page.goto(members_url)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        new_profiles = set()
        for a in soup.find_all("a", href=True):
            if re.match(r"^/users/\d+", a["href"]):
                profile_url = "https://11x11.ru" + a["href"]
                nickname = a.get_text(strip=True)
                if not nickname:
                    # Если текст ссылки пуст, возьмем часть URL
                    nickname = profile_url.split("/")[-1]
                new_profiles.add( (profile_url, nickname) )
        if not new_profiles:
            break
        profiles.update(new_profiles)
        pagenum += 1
    return list(profiles)

def main():
    st.title("11x11 Статистика (Playwright)")
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
        # Новые данные для входа:
        login = "лао"
        password = "111333555"
        
        computed_stats = {}
        results = []  # Список для хранения результатов каждого профиля
        computed_nicknames = {}  # Для кэширования никнеймов (если потребуется)
        
        # Контейнер для обновления таблицы
        table_placeholder = st.empty()
        
        with sync_playwright() as p:
            # Запускаем Chromium в headless‑режиме (без параметра executable_path)
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://11x11.ru/")
            page.fill("input[name='auth_name']", login)
            page.fill("input[name='auth_pass1']", password)
            page.click("xpath=//input[@type='submit' and @value='Войти']")
            page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]")
            
            # Если выбран режим "Профилю" – обрабатываем один профиль
            if mode_choice == "Профилю":
                nickname = get_nickname(page, target_url)
                wins, draws, losses = collect_stats_for_profile(page, target_url, filter_from, filter_to, computed_stats)
                profile_link = f'<a href="{target_url}" target="_blank">{nickname}</a>'
                results.append({
                    "Профиль": profile_link,
                    "Побед": wins,
                    "Ничьих": draws,
                    "Поражений": losses
                })
                # Выводим таблицу с гиперссылками через HTML
                df = pd.DataFrame(results)
                table_placeholder.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
            else:
                # Режим "Союз": получаем список членов
                profile_tuples = get_profiles_from_guild(page, target_url)
                if not profile_tuples:
                    st.write("Не удалось получить профили из союза.")
                else:
                    total_wins = total_draws = total_losses = 0
                    for (url, member_nick) in profile_tuples:
                        wins, draws, losses = collect_stats_for_profile(page, url, filter_from, filter_to, computed_stats)
                        total_wins += wins
                        total_draws += draws
                        total_losses += losses
                        profile_link = f'<a href="{url}" target="_blank">{member_nick}</a>'
                        results.append({
                            "Профиль": profile_link,
                            "Побед": wins,
                            "Ничьих": draws,
                            "Поражений": losses
                        })
                        # Обновляем таблицу после обработки каждого профиля
                        df = pd.DataFrame(results)
                        table_placeholder.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
                    # Добавляем итоговую строку
                    results.append({
                        "Профиль": "<b>Итого</b>",
                        "Побед": total_wins,
                        "Ничьих": total_draws,
                        "Поражений": total_losses
                    })
                    df = pd.DataFrame(results)
                    table_placeholder.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
            context.close()
            browser.close()

if __name__ == "__main__":
    main()
