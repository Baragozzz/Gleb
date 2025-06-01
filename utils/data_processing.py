import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import streamlit as st
from playwright.async_api import async_playwright, TimeoutError

async def async_get_nickname(page, profile_url):
    """Получает никнейм пользователя по ссылке профиля."""
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
        title_text = title_tag.get_text().strip()
        if "Профиль участника" in title_text:
            return title_text.replace("Профиль участника", "").split("–")[0].strip()

    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True).split("–")[0].strip()

    return profile_url.split("/")[-1]

async def async_collect_stats_for_profile(page, profile_url, filter_from, filter_to, computed_stats):
    """Собирает статистику матчей профиля: победы, ничьи, поражения."""
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
        except Exception:
            break

        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr")
        if not rows:
            break

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue

            date_str = cols[0].get_text(strip=True)
            try:
                match_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")
            except ValueError:
                continue

            if match_date < filter_from:
                break
            if match_date > filter_to:
                continue

            result = "Draw"
            center = cols[2]
            b_tag = center.find("b")
            if b_tag and b_tag.find("a"):
                href = b_tag.find("a")["href"]
                result = "Win" if user_id in href else "Loss"

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
            profile_urls = []
            guild_id_match = re.search(r'/guilds/(\d+)', target_url)
            if not guild_id_match:
                return []

            guild_id = guild_id_match.group(1)
            page_num = 1

            while True:
                guild_url = f"https://11x11.ru/xml/misc/guilds.php?page={page_num}&type=misc/guilds&act=members&id={guild_id}"
                await page.goto(guild_url, timeout=15000, wait_until="domcontentloaded")
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                new_profiles = {f"https://11x11.ru{a['href']}" for a in soup.find_all("a", href=True) if re.match(r"^/users/\d+", a["href"])}

                if not new_profiles - set(profile_urls):
                    break

                profile_urls.extend(new_profiles)
                page_num += 1

            semaphore = asyncio.Semaphore(10)
            async def sem_process(profile_url):
                async with semaphore:
                    return await process_profile(context, profile_url, filter_from, filter_to, computed_stats)

            profiles_results = await asyncio.gather(*[sem_process(url) for url in profile_urls])
            dedup = {re.search(r'/users/(\d+)', pr[0]).group(1): pr for pr in profiles_results if re.search(r'/users/\d+', pr[0])}
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
