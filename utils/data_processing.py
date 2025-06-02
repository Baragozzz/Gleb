import asyncio
import re
from bs4 import BeautifulSoup
from datetime import datetime
import streamlit as st
from playwright.async_api import async_playwright, TimeoutError

def clean_nickname(nickname: str) -> str:
    """
    Очищает строку с никнеймом:
      - Убирает префикс "Профиль участника", если присутствует.
      - Разбивает по символу тире или дефису и оставляет первую часть.
    """
    nickname = nickname.strip()
    if nickname.startswith("Профиль участника"):
        nickname = nickname.replace("Профиль участника", "").strip()
    parts = re.split(r"[-–]", nickname)
    if parts:
        return parts[0].strip()
    return nickname

async def async_get_nickname_request(context, profile_url: str) -> str:
    """
    Быстрый способ получить никнейм без создания новой вкладки,
    используя HTTP-запрос через context.request.get.
    """
    response = await context.request.get(profile_url)
    html = await response.text()
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if title_tag:
        return clean_nickname(title_tag.get_text(strip=True))
    h1 = soup.find("h1")
    if h1:
        return clean_nickname(h1.get_text(strip=True))
    return profile_url.split("/")[-1]

async def async_collect_stats_for_profile_request(context, profile_url: str, filter_from: datetime, filter_to: datetime, computed_stats: dict):
    """
    Без создания новой вкладки получает статистику матчей профиля через HTTP-запросы.
    """
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
        response = await context.request.get(history_url)
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("tr")
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

async def process_profile_request(context, profile_url: str, filter_from: datetime, filter_to: datetime, computed_stats: dict):
    """
    Объединённая функция для получения никнейма и статистики профиля посредством HTTP-запросов.
    """
    nickname = await async_get_nickname_request(context, profile_url)
    wins, draws, losses = await async_collect_stats_for_profile_request(context, profile_url, filter_from, filter_to, computed_stats)
    return profile_url, nickname, wins, draws, losses

async def async_get_profiles_from_guild(context, guild_url: str):
    """
    Быстрый метод получения списка участников союза с использованием HTTP-запросов.
    """
    guild_id_match = re.search(r'/guilds/(\d+)', guild_url)
    if not guild_id_match:
        return []
    guild_id = guild_id_match.group(1)
    profiles = set()
    page_num = 1
    while True:
        members_url = f"https://11x11.ru/xml/misc/guilds.php?page={page_num}&type=misc/guilds&act=members&id={guild_id}"
        response = await context.request.get(members_url)
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        new_profiles = { (f"https://11x11.ru{a['href']}", a.get_text(strip=True))
                         for a in soup.select("a[href^='/users/']") }
        if not new_profiles - profiles:
            break
        profiles.update(new_profiles)
        page_num += 1
    return list(profiles)

async def async_main(mode_choice: str, target_url: str, filter_from: datetime, filter_to: datetime, login: str, password: str):
    """
    Главная асинхронная функция для сбора статистики.
    Для одиночного профиля и для союза используются методы на базе context.request.get,
    что позволяет существенно ускорить получение данных.
    """
    computed_stats = {}
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        # Авторизация выполняется на странице, затем закрывается она — далее все запросы через context.request:
        page = await context.new_page()
        await page.goto("https://11x11.ru/", timeout=15000, wait_until="domcontentloaded")
        await page.fill("input[name='auth_name']", login)
        await page.fill("input[name='auth_pass1']", password)
        await page.click("xpath=//input[@type='submit' and @value='Войти']")
        await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)
        await page.close()
        
        if mode_choice == "Профилю":
            profile_url, nickname, wins, draws, losses = await process_profile_request(context, target_url, filter_from, filter_to, computed_stats)
            results.append({
                "Профиль": f'<a href="{profile_url}" target="_blank">{nickname}</a>',
                "Побед": wins,
                "Ничьих": draws,
                "Поражений": losses
            })
        else:
            profile_tuples = await async_get_profiles_from_guild(context, target_url)
            if not profile_tuples:
                await context.close()
                await browser.close()
                return []
            tasks = [process_profile_request(context, url, filter_from, filter_to, computed_stats)
                     for (url, _) in profile_tuples]
            profiles_results = await asyncio.gather(*tasks)
            dedup = { re.search(r'/users/(\d+)', pr[0]).group(1): pr for pr in profiles_results if re.search(r'/users/\d+', pr[0]) }
            profiles_results = list(dedup.values())
            total_players = len(profiles_results)
            active_count = sum(1 for (_, _, w, d, l) in profiles_results if (w + d + l) > 0)
            inactive_count = total_players - active_count
            for profile_url, nickname, wins, draws, losses in profiles_results:
                results.append({
                    "Профиль": f'<a href="{profile_url}" target="_blank">{nickname}</a>',
                    "Побед": wins,
                    "Ничьих": draws,
                    "Поражений": losses
                })
            results.append({
                "Профиль": f"<b>Всего игроков: {total_players}, играли: {active_count}, не играли: {inactive_count}</b>",
                "Побед": "",
                "Ничьих": "",
                "Поражений": ""
            })
        await context.close()
        await browser.close()
    return results
