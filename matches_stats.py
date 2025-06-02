import streamlit as st
from pages.statistics import statistics_page
from pages.roster import roster_page
import os

# Если требуется установить playwright (однократно), можно оставить эту строку:
os.system("playwright install")

def home_page():
    st.title("Добро пожаловать в 11x11 Статистика!")
    st.markdown("""
    Это приложение предназначено для анализа и мониторинга статистики 11x11.

    **Разделы приложения:**
    - **Статистика матчей:** Анализируйте результаты матчей для отдельных профилей или союзов.
    - **Ростер игроков:** Просматривайте состав союза, а также метрики вроде *Сила 11 лучших* и *Ср. сила 11 лучших*.

    Используйте вкладки ниже для навигации по разделам.
    """)

def main():
    st.title("11x11 Статистика")
    
    # Создаем три вкладки: домашняя, статистика матчей и ростер игроков.
    tab_home, tab_stats, tab_roster = st.tabs(["Домашняя", "Статистика матчей", "Ростер игроков"])
    
    with tab_home:
        home_page()
    with tab_stats:
        statistics_page()
    with tab_roster:
        roster_page()

if __name__ == "__main__":
    main()
