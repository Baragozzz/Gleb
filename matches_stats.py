import streamlit as st
from pages.roster import roster_page
import os
os.system("playwright install")

def main():
    st.title("11x11 Статистика")
    # Вызываем только страницу "Ростер игроков"
    roster_page()

if __name__ == "__main__":
    main()
