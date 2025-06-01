import streamlit as st
import subprocess
import re
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

def collect_stats_for_profile(page, profile_url, filter_from, filter_to, computed_stats):
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
            pass  # Если страница-load не завершилась, продолжаем
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
                new_profiles.add("https://11x11.ru" + a["href"])
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
        results = []  # Для хранения результатов каждого профиля
        
        # Контейнер для обновления таблицы
        table_placeholder = st.empty()
        
        with sync_playwright() as p:
            # Запускаем Chromium в headless‑режиме без явного указания пути к бинарнику
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto("https://11x11.ru/")
            page.fill("input[name='auth_name']", login)
            page.fill("input[name='auth_pass1']", password)
            page.click("xpath=//input[@type='submit' and @value='Войти']")
            page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]")
            
            if mode_choice == "Профилю":
                wins, draws, losses = collect_stats_for_profile(page, target_url, filter_from, filter_to, computed_stats)
                results.append({
                    "Профиль": target_url,
                    "Побед": wins,
                    "Ничьих": draws,
                    "Поражений": losses
                })
                table_placeholder.table(results)
            else:
                profile_urls = get_profiles_from_guild(page, target_url)
                if not profile_urls:
                    st.write("Не удалось получить профили из союза.")
                else:
                    total_wins = total_draws = total_losses = 0
                    for url in profile_urls:
                        wins, draws, losses = collect_stats_for_profile(page, url, filter_from, filter_to, computed_stats)
                        results.append({
                            "Профиль": url,
                            "Побед": wins,
                            "Ничьих": draws,
                            "Поражений": losses
                        })
                        total_wins += wins
                        total_draws += draws
                        total_losses += losses
                        # Обновляем таблицу после обработки каждого профиля
                        table_placeholder.table(results)
                    # Добавляем итоговую строку
                    results.append({
                        "Профиль": "Итого",
                        "Побед": total_wins,
                        "Ничьих": total_draws,
                        "Поражений": total_losses
                    })
                    table_placeholder.table(results)
            context.close()
            browser.close()

if __name__ == "__main__":
    main()
