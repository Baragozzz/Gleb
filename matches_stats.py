import streamlit as st
from pages.statistics import statistics_page
from pages.roster import roster_page
import os

# Если требуется одноразовая установка playwright:
os.system("playwright install")

def home_page():
    st.title("Добро пожаловать в 11x11 Статистика!")
    # Добавляем GIF (можно заменить URL на свой или указать путь к локальному файлу GIF)
    st.image(
    "https://i.gifer.com/1uzh.gif",
    caption="Добро пожаловать!",
    use_container_width=True)
    st.markdown("""
    Это приложение предназначено для анализа и мониторинга статистики 11x11.

    **Разделы приложения:**
    - **Статистика матчей:** Анализируйте результаты матчей.
    - **Ростер игроков:** Просматривайте состав союза и метрики игроков.

    Используйте вкладки выше для навигации по разделам.
    """)

def main():
    st.title("11x11 Статистика")
    # Создаем вкладки, которые отображаются в верхней части интерфейса
    tab_home, tab_stats, tab_roster = st.tabs(["Домашняя", "Статистика матчей", "Ростер игроков"])
    
    with tab_home:
        home_page()
    with tab_stats:
        statistics_page()
    with tab_roster:
        roster_page()

if __name__ == "__main__":
    main()
