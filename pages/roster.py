import streamlit as st

def roster_page():
    """Страница ростера игроков"""
    st.subheader("Ростер игроков")

    st.write("Введите URL союза:")
    target_url = st.text_input("URL союза:", value="https://11x11.ru/guilds/139")

    if st.button("Получить ростер"):
        st.write("🕒 Загружаем список игроков...")
        # Здесь можно добавить код для парсинга списка игроков
        st.write("✅ Готово! Здесь будет список игроков.")
