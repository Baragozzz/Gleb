import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import streamlit as st  # ✅ Добавляем для проверки!

async def async_main(mode_choice, target_url, filter_from, filter_to, login, password):
    """Асинхронная обработка статистики матчей"""

    session = requests.Session()
    auth_url = "https://11x11.ru/login"
    auth_data = {"login": login, "password": password}
    session.post(auth_url, data=auth_data)

    response = session.get(target_url)
    if response.status_code != 200:
        st.write("❌ Ошибка загрузки страницы:", response.status_code)
        return []

    st.write("✅ Загружена страница:", response.text[:500])  # ✅ Выводим первые 500 символов HTML

    soup = BeautifulSoup(response.text, "html.parser")
    
    matches_data = []
    matches = soup.find_all("div", class_="match-row")  # ✅ Выводим найденные матчи!
    
    st.write("📊 Найдено матчей:", len(matches))  # ✅ Проверяем количество матчей

    for match in matches:
        date_str = match.find("span", class_="match-date").text.strip()  # ✅ Проверяем дату!
        match_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")

        st.write("📅 Матч:", match_date, "| Фильтр:", filter_from, "-", filter_to)  # ✅ Проверяем даты

        if filter_from <= match_date <= filter_to:
            player = match.find("span", class_="player-name").text.strip()
            result = match.find("span", class_="match-result").text.strip()

            matches_data.append({
                "Игрок": player,
                "Дата": match_date.strftime("%d.%m.%Y %H:%M"),
                "Результат": result,
            })

    st.write("✅ Итоговые данные:", matches_data)  # ✅ Финальный вывод

    return matches_data
