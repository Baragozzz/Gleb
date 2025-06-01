import streamlit as st
from pages.statistics import statistics_page
from pages.roster import roster_page

def main():
    st.title("11x11 Статистика")

    # Создание вкладок
    tab1, tab2 = st.tabs(["Статистика матчей", "Ростер игроков"])

    with tab1:
        statistics_page()

    with tab2:
        roster_page()

if __name__ == "__main__":
    main()