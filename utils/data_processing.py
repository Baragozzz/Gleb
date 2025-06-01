import asyncio
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import streamlit as st
from playwright.async_api import async_playwright, TimeoutError

async def async_get_nickname(page, profile_url):
    """Получает никнейм пользователя по ссылке профиля."""
    try:
        await page.goto(profile_url, timeout=15000, wait_until="domcontentloaded")
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True).split("–")[0].strip()

        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True).split("–")[0].strip()
    except TimeoutError:
        return profile_url.split("/")[-1]

    return profile_url.split("/")[-1]

async def async_collect_stats_for_profile(page, profile_url, filter_from, filter_to, computed_stats):
    """Собирает статистику матчей профиля."""
    user_id_match = re.search(r'/users/(\d+)', profile_url)
    if not user_id_match:
        return (0, 0, 0)
    
    user_id = user_id_match.group(1)
    if user_id in computed_stats:
        return computed_stats[user_id]

    wins, draws, losses = 0, 0, 0
    page_num = 1

    while True:
        history_url = f"https://11x11.ru/xml/games/history.php?page={page_num}&act=userhistory&user={user_id}"
        try:
            await page.goto(history_url, timeout=15000, wait_until="domcontentloaded")
            soup = BeautifulSoup(await page.content(), "html.parser")
            rows = soup.select("tr")
        except Exception:
            break

        if not rows:
            break

        for row in rows:
            cols = row.select("td")
            if len(cols) < 4:
                continue

            try:
                match_date = datetime.strptime(cols[0].get_text(strip=True), "%d.%m.%Y %H:%M")
                if match_date < filter_from:
                    return wins, draws, losses
                if match_date > filter_to:
                    continue
            except ValueError:
                continue

            result = "Draw"
            center = cols[2].select_one("b a")
            if center and user_id in center["href"]:
                result = "Win"
            elif center:
                result = "Loss"

            if result == "Win":
                wins += 1
            elif result == "Loss":
                losses += 1
            else:
                draws += 1

        page_num += 1

    computed_stats[user_id] = (wins, draws, losses)
    return wins, draws, losses

async def process_profile(context, profile_url, filter_from, filter_to, computed_stats):
    """Создаёт новую вкладку для профиля, получает ник и статистику."""
    page = await context.new_page()
    nickname = await async_get_nickname(page, profile_url)
    wins, draws, losses = await async_collect_stats_for_profile(page, profile_url, filter_from, filter_to, computed_stats)
    await page.close()
    return profile_url, nickname, wins, draws, losses

async def async_main(mode_choice, target_url, filter_from, filter_to, login, password):
    """Асинхронно собирает статистику матчей."""
    computed_stats = {}
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto
