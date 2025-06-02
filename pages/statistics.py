import streamlit as st
import subprocess
import re
import pandas as pd
import asyncio
from datetime import datetime
from bs4 import BeautifulSoup
from utils.data_processing import async_get_profiles_from_guild
from playwright.async_api import async_playwright, TimeoutError
from utils.data_processing import async_main


# Попытка установки Chromium (если ещё не установлен)
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    st.write("Ошибка установки playwright chromium:", e)

def parse_date(date_str):
    """Преобразует строку 'ДД.ММ.ГГГГ ЧЧ:ММ' в объект datetime."""
    return datetime.strptime(date_str, "%d.%m.%Y %H:%M")

def clean_nickname(raw_text):
    """Очищает никнейм, убирая лишние элементы."""
    nickname = raw_text.strip()
    if "Профиль участника" in nickname:
        nickname = nickname.replace("Профиль участника", "").strip()
    if "–" in nickname:
        nickname = nickname.split("–")[0].strip()
    elif "-" in nickname:
        nickname = nickname.split("-")[0].strip()
    return nickname

async def process_profile(context, profile_url, filter_from, filter_to, computed_stats):
    """Создаёт новую вкладку для профиля, получает ник и статистику."""
    page = await context.new_page()
    nickname = await async_get_nickname(page, profile_url)
    wins, draws, losses = await async_collect_stats_for_profile(page, profile_url, filter_from, filter_to, computed_stats)
    await page.close()
    return profile_url, nickname, wins, draws, losses

async def async_main(mode_choice, target_url, filter_from, filter_to, login, password):
    """Асинхронно собирает статистику матчей"""
    computed_stats = {}
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
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
            profile_url, nickname, wins, draws, losses = await process_profile(context, target_url, filter_from, filter_to, computed_stats)
            results.append({
                "Профиль": f'<a href="{profile_url}" target="_blank">{nickname}</a>',
                "Побед": wins,
                "Ничьих": draws,
                "Поражений": losses
            })
        else:
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

            dedup = {}
            for pr in profiles_results:
                profile_url, nickname, wins, draws, losses = pr
                match = re.search(r'/users/(\d+)', profile_url)
                if not match:
                    continue
                user_id = match.group(1)
                if nickname.strip().lower() in ["профиль", "лао"]:
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

def statistics_page():
    """Страница статистики матчей"""
    st.subheader("Статистика матчей")

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
        st.write("🕒 Анализ данных...")

        try:
            results = asyncio.run(async_main(mode_choice, target_url, filter_from, filter_to, login, password))
        except RuntimeError:
            st.write("❌ Ошибка: `asyncio.run()` нельзя вызывать внутри уже работающего event loop.")
            return

        if results:
            df = pd.DataFrame(results)
            st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.write("Нет результатов.")
