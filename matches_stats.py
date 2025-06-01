import streamlit as st
import time, re
from datetime import datetime
from collections import defaultdict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

def parse_date(date_str):
    return datetime.strptime(date_str, "%d.%m.%Y %H:%M")

def collect_stats_for_profile(profile_url, filter_from, filter_to, driver, computed_stats):
    user_id_match = re.search(r'/users/(\d+)', profile_url)
    if not user_id_match:
        st.write(f"Неверный URL профиля: {profile_url}")
        return (0, 0, 0)
    user_id = user_id_match.group(1)
    if user_id in computed_stats:
        return computed_stats[user_id]
    wins = 0
    draws = 0
    losses = 0
    page_num = 1
    while True:
        history_url = f"https://11x11.ru/xml/games/history.php?page={page_num}&type=games/history&act=userhistory&user={user_id}"
        driver.get(history_url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        found_match = False
        stop = False
        for row in soup.find_all("tr"):
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

def get_profiles_from_guild(guild_url, driver):
    guild_id_match = re.search(r'/guilds/(\d+)', guild_url)
    if not guild_id_match:
        st.write("Неверный URL союза.")
        return []
    guild_id = guild_id_match.group(1)
    profiles = set()
    page = 1
    while True:
        members_url = f"https://11x11.ru/xml/misc/guilds.php?page={page}&type=misc/guilds&act=members&id={guild_id}"
        driver.get(members_url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        new_profiles = set()
        for a in soup.find_all("a", href=True):
            if re.match(r"^/users/\d+", a["href"]):
                new_profiles.add("https://11x11.ru" + a["href"])
        if not new_profiles:
            break
        profiles.update(new_profiles)
        page += 1
    return list(profiles)

def main():
    st.title("11x11 Статистика")
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
        login = "Мечтатель"
        password = "31#!Baragoz"
        driver = webdriver.Chrome(ChromeDriverManager().install())
        wait = WebDriverWait(driver, 20)
        driver.get("https://11x11.ru/")
        wait.until(EC.presence_of_element_located((By.NAME, "auth_name"))).send_keys(login)
        driver.find_element(By.NAME, "auth_pass1").send_keys(password)
        driver.find_element(By.XPATH, '//input[@type="submit" and @value="Войти"]').click()
        wait.until(EC.presence_of_element_located((By.XPATH, '//a[contains(text(), "Выход")]')))
        computed_stats = {}
        if mode_choice == "Профилю":
            wins, draws, losses = collect_stats_for_profile(target_url, filter_from, filter_to, driver, computed_stats)
            st.write("Профиль:", target_url)
            st.write("Побед:", wins)
            st.write("Ничьих:", draws)
            st.write("Поражений:", losses)
        else:
            profile_urls = get_profiles_from_guild(target_url, driver)
            if not profile_urls:
                st.write("Не удалось получить профили из союза.")
            else:
                total_wins = total_draws = total_losses = 0
                st.write("Найдено профилей:", len(profile_urls))
                for url in profile_urls:
                    wins, draws, losses = collect_stats_for_profile(url, filter_from, filter_to, driver, computed_stats)
                    st.write("Профиль:", url, "Побед:", wins, "Ничьих:", draws, "Поражений:", losses)
                    total_wins += wins
                    total_draws += draws
                    total_losses += losses
                st.write("Общая статистика по союзу:")
                st.write("Побед:", total_wins)
                st.write("Ничьих:", total_draws)
                st.write("Поражений:", total_losses)
        driver.quit()

if __name__ == "__main__":
    main()
