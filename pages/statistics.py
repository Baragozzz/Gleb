import streamlit as st
import asyncio
import subprocess
import re
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError

# Попытка динамически установить Chromium (если ещё не установлен)
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    st.write("Ошибка установки Playwright Chromium:", e)

def parse_date(date_str):
    """Преобразует строку 'ДД.ММ.ГГГГ ЧЧ:ММ' в объект datetime."""
    return datetime.strptime(date_str, "%d.%m.%Y %H:%M")

def clean_nickname(raw_text):
    """Очищает текст никнейма."""
    nickname = raw_text.strip()
    if "Профиль участника" in nickname:
        nickname = nickname.replace("Профиль участника", "").strip()
    if "–" in nickname:
        nickname = nickname.split("–")[0].strip()
    elif "-" in nickname:
        nickname = nickname.split("-")[0].strip()
    return nickname

async def async_main(mode_choice, target_url, filter_from, filter_to, login, password):
    """Асинхронная обработка статистики матчей"""
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
            profile_url, nickname
