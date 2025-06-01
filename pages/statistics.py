import streamlit as st
import asyncio
import pandas as pd
from datetime import datetime
from matches_stats import async_main  # Подключение вашей существующей логики

def statistics_page():
    """Полностью восстановленная страница статистики матчей"""
    st.subheader("Статистика матчей")

    # Выбор режима: профиль или союз (как раньше)
    mode_choice = st.selectbox("Строить статистику по:", ("Профилю", "Союзу"))
    period_mode = st.selectbox("Режим периода", ("День", "Интервал"))

    # Выбор даты или диапазона дат (как раньше)
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

    # Ввод URL профиля или союза (как раньше)
    if mode_choice == "Профилю":
        target_url = st.text_input("Введите URL профиля:", value="https://11x11.ru/users/3941656")
    else:
        target_url = st.text_input("Введите URL союза:", value="https://11x11.ru/guilds/139")

    if st.button("Собрать статистику"):
        login = "лао"
        password = "111333555"
        st.write("🕒 Анализ данных...")

        # Запуск вашего существующего асинхронного сбора данных
        results = asyncio.run(async_main(mode_choice, target_url, filter_from, filter_to, login, password))

        # Вывод результатов в виде таблицы (как раньше)
        if results:
            df = pd.DataFrame(results)
            st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.write("Нет результатов.")
