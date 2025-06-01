import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime

async def async_main(mode_choice, target_url, filter_from, filter_to, login, password):
    """Асинхронная обработка статистики матчей"""

    # 🔹 Авторизация (если требуется)
    session = requests.Session()
    auth_url = "https://11x11.ru/login"
    auth_data = {"login": login, "password": password}
    session.post(auth_url, data=auth_data)

    # 🔹 Запрос данных со страницы
    response = session.get(target_url)
    if response.status_code != 200:
        print("❌ Ошибка загрузки страницы:", response.status_code)
        return []

    print("✅ Загружена страница:", response.text[:500])  # Проверяем первые 500 символов HTML

    # 🔹 Парсинг страницы
    soup = BeautifulSoup(response.text, "html.parser")
    
    # 🔹 Поиск информации по матчам
    matches_data = []
    matches = soup.find_all("div", class_="match-row")  # Замените на реальный HTML-класс
    
    print("📊 Найдено матчей:", len(matches))  # Проверяем, сколько матчей найдено

    for match in matches:
        date_str = match.find("span", class_="match-date").text.strip()  # Замените на реальный HTML-класс
        match_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M")

        print("📅 Матч:", match_date, "| Фильтр:", filter_from, "-", filter_to)  # Проверяем даты

        # 🔹 Фильтр по выбранному диапазону дат
        if filter_from <= match_date <= filter_to:
            player = match.find("span", class_="player-name").text.strip()
            result = match.find("span", class_="match-result").text.strip()

            matches_data.append({
                "Игрок": player,
                "Дата": match_date.strftime("%d.%m.%Y %H:%M"),
                "Результат": result,
            })

    print("✅ Итоговые данные:", matches_data)  # Проверяем, что парсинг работает

    return matches_data  # Возвращаем обработанные данные
