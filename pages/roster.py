def roster_page():
    st.title("Ростер игроков")
    guild_url = st.text_input("Введите URL союза:", value="https://11x11.ru/guilds/139")
    login = "лао"
    password = "111333555"

    if st.button("Получить ростер"):
        with st.spinner("Загружаем ростер игроков..."):
            try:
                loop = asyncio.get_event_loop()
                alliance_name, roster = loop.run_until_complete(async_get_roster(guild_url, login, password))
            except Exception as e:
                st.error(f"Ошибка: {e}")
                return

        st.markdown(f"### Союз: {alliance_name}")

        if roster:
            # Формируем таблицу (DataFrame) из полученных данных
            data = []
            for profile_url, nickname, power, avg_power in roster:
                data.append({
                    "Профиль": f'<a href="{profile_url}" target="_blank">{nickname}</a>',
                    "Сила 11 лучших": power,
                    "Ср. сила 11 лучших": avg_power,
                })
            df = pd.DataFrame(data)

            st.markdown("#### Фильтры и сортировка")
            # Попытаемся привести колонку "Сила 11 лучших" к числовому типу.
            # Игнорируются ошибки, если значение не конвертируется (то есть останется NaN).
            df["Сила 11 лучших (число)"] = pd.to_numeric(df["Сила 11 лучших"], errors="coerce")

            # Задаем минимальное и максимальное значение для слайдера.
            min_val = int(df["Сила 11 лучших (число)"].min() or 0)
            max_val = int(df["Сила 11 лучших (число)"].max() or 10000)

            threshold = st.slider(
                "Минимальная Сила 11 лучших", 
                min_value=min_val, 
                max_value=max_val, 
                value=min_val,
                key="power_filter"
            )

            sort_order = st.selectbox(
                "Сортировка", 
                ("Без сортировки", "По возрастанию", "По убыванию")
            )

            # Применяем фильтрацию
            df_filtered = df[df["Сила 11 лучших (число)"] >= threshold].copy()

            # Применяем сортировку по выбранному порядку
            if sort_order == "По возрастанию":
                df_filtered = df_filtered.sort_values("Сила 11 лучших (число)")
            elif sort_order == "По убыванию":
                df_filtered = df_filtered.sort_values("Сила 11 лучших (число)", ascending=False)

            # Убираем временную колонку с числовыми значениями
            df_filtered.drop(columns=["Сила 11 лучших (число)"], inplace=True)

            st.markdown("#### Результаты")
            # Выводим таблицу с HTML-ссылками (unsafe_allow_html=True чтобы ссылки работали)
            st.markdown(
                df_filtered.to_html(escape=False, index=False),
                unsafe_allow_html=True
            )
        else:
            st.write("Нет результатов.")
