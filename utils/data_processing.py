async def async_main(mode_choice, target_url, filter_from, filter_to, login, password):
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

        try:
            await page.wait_for_selector("xpath=//a[contains(text(), 'Выход')]", timeout=15000)
        except Exception as e:
            st.error("Ошибка авторизации: элемент 'Выход' не найден. Проверьте правильность логина/пароля или изменился дизайн страницы.")
            return []

        # Далее – логика обработки профиля или союза
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
            dedup = { re.search(r'/users/(\d+)', pr[0]).group(1): pr for pr in profiles_results if re.search(r'/users/\d+', pr[0]) }
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
