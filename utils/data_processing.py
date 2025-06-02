import asyncio
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import streamlit as st
from playwright.async_api import async_playwright, TimeoutError

def clean_nickname(nickname):
    """
    Очищает строку с никнеймом:
    - Удаляет префикс "Профиль участника" (если присутствует).
    - Разбивает строку по символам тире (как en-dash, так и обычный дефис) и оставляет первую часть.
    """
    nickname = nickname.strip()
    if nickname.startswith("Профиль участника"):
        nickname = nickname.replace("Профиль участника", "").strip()
    # Разбиваем по символам тире (–) или дефису (-)
    parts = re.split(r"[-–]", nickname)
    if parts:
        return parts[0].strip()
    return nickname

async def async_get_nickname(page, profile_url):
    """Получает никнейм пользователя по ссылке профиля."""
    try:
        await page.goto(profile_url, timeout=15000, wait_until="domcontentloaded")
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.find("title")
        if title_tag:
            return clean_nickname(title_tag.get_text(strip=True))

        h1 = soup.find("h1")
        if h1:
            return clean_nickname(h1.get_text(strip=True))
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

async def async_get_profiles_from_guild(page, guild_url):
    """Асинхронно получает список участников союза."""
    guild_id_match = re.search(r'/guilds/(\d+)', guild_url)
    if not guild_id_match:
        return []
    guild_id = guild_id_match.group(1)
    profiles = set()
    page_num = 1
    while True:
        members_url = f"https://11x11.ru/xml/misc/guilds.php?page={page_num}&type=misc/guilds&act=members&id={guild_id}"
        try:
            await page.goto(members_url, timeout=15000, wait_until="domcontentloaded")
            soup = BeautifulSoup(await page.content(), "html.parser")
            new_profiles = {(f"https://11x11.ru{a['href']}", a.get_text(strip=True))
                             for a in soup.select("a[href^='/users/']")}
        except Exception:
            break
        if not new_profiles - profiles:
            break
        profiles.update(new_profiles)
        page_num += 1
    return list(profiles)

async def async_main(mode_choice, target_url, filter_from, filter_to, login, password):
    """Асинхронно собирает статистику матчей."""
    computed_stats = {}
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Авторизация на сайте
        await page.goto("https://11x11.ru/", timeout=15000, wait_until="domcontentloaded")
        await page.fill("input[name='auth_name']", login)
        await page.fill("input[name='auth_pass1']", password)
        await page.click("xpath=//input[@type='submit' and @value='Войти']")
        await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)

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
            dedup = { re.search(r'/users/(\d+)', pr[0]).group(1): pr for pr in profiles_results 
                     if re.search(r'/users/\d+', pr[0]) }
            profiles_results = dedup.values()
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

        await page.close()
        await context.close()
        await browser.close()
    return results
