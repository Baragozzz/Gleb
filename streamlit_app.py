import streamlit as st

xp_table = {
    3: 30,
    4: 90,
    5: 190,
    6: 340,
    7: 540,
    8: 840,
    9: 1240,
    10: 1790,
    11: 2540,
    12: 3540,
    13: 5040,
    14: 7040,
    15: 10040,
    16: 14040,
    17: 19540,
    18: 27040,
    19: 37040,
    20: 52040,
    21: 72040,
    22: 10740,
    23: 157040,
    24: 232040,
    25: 332040,
    26: 482040,
    27: 682040,
    28: 1032040,
    29: 1532040,
    30: 2282040,
    31: 3282040,
    32: 4532040,
    33: 6032040,
    34: 7832040,
    35: 9932040,
    36: 12332040,
    37: 15032040,
    38: 18032040,
    39: 21532040,
    40: 25532040,
    41: 30332040,
    42: 35932040,
    43: 42332040,
    44: 49532040,
    45: 57532040,
    46: 66332040,
    47: 75932040,
    48: 86332040,
    49: 97532040,
    50: 109532040,
    51: 123032040,
    52: 138032040,
    53: 154532040,
    54: 172532040,
    55: 192532040,
    56: 214532040,
    57: 239532040,
    58: 267532040,
    59: 299532040,
    60: 336532040
}

default_levels = {
    "От": 2,
    "Оп": 2,
    "Др": 2,
    "Пм": 2,
    "Вн": 2,
    "Пс": 2,
    "Сл": 2,
    "Тч": 2
}
class XPTable:
    def __init__(self, xp_data: dict):
        self.xp_data = xp_data

    def xp_between(self, start_level, end_level):
        return self.xp_data.get(end_level, 0) - self.xp_data.get(start_level, 0)


class Player:
    def __init__(self, name: str, levels: dict, xp_table: XPTable, unspent_xp: int = 0):
        self.name = name
        self.levels = levels
        self.xp_table = xp_table
        self.unspent_xp = unspent_xp

    def distributed_xp(self):
        return sum(self.xp_table.xp_between(2, lvl) for lvl in self.levels.values())

    def total_xp_accumulated(self):
        return self.distributed_xp() + self.unspent_xp

    def total_xp_remaining(self):
        raw_remaining = sum(self.xp_table.xp_between(lvl, 60) for lvl in self.levels.values())
        return max(raw_remaining - self.unspent_xp, 0)
    
    def summary(self):
        print(f"Игрок: {self.name}")
        print("-" * 40)
        print("Уровни характеристик:")
        for stat, lvl in self.levels.items():
            print(f"  {stat}: {lvl}")
        print("-" * 40)
        print(f"Распределённый опыт: {self.distributed_xp():,}")
        print(f"Нераспределённый опыт: {self.unspent_xp:,}")
        print(f"Общий накопленный опыт: {self.total_xp_accumulated():,}")
        print(f"Осталось до максимума: {self.total_xp_remaining():,}")
        print("=" * 40)

    def summary_row(self):
        return {
            "Имя": self.name,
            "Распределённый опыт": self.distributed_xp(),
            "Нераспределённый опыт": self.unspent_xp,
            "Всего опыта": self.total_xp_accumulated(),
            "Осталось до макс.": self.total_xp_remaining()
        }
xp_x = XPTable(xp_data=xp_table)

def create_player(name: str, custom_levels: dict, xp_table: XPTable, unspent_xp: int = 0) -> Player:
    full_levels = default_levels.copy()
    full_levels.update(custom_levels)
    return Player(name=name, levels=full_levels, xp_table=xp_table, unspent_xp=unspent_xp)

players = [
    create_player("Макаке", {"От": 50, "Оп": 50, "Вн": 37}, xp_x, unspent_xp=946350494),
    create_player("Макаков", {"От": 40, "Оп": 10, "Вн": 37}, xp_x, unspent_xp=603663996),
    create_player("Макакелли", {"От": 40, "Оп": 10, "Вн": 37}, xp_x, unspent_xp=1255048619),
    create_player("Макакян", {"От": 50, "Оп": 50, "Вн": 37}, xp_x, unspent_xp=1330630311),
    create_player("Макакич", {"Др": 25, "Пм": 30, "Вн": 37, "Пс": 40}, xp_x, unspent_xp=685312555),
    create_player("Макакис", {"Др": 30, "Пм": 25, "Вн": 37, "Пс": 40}, xp_x, unspent_xp=616855888),
    create_player("Макакава", {"Др": 30, "Пм": 20, "Вн": 37, "Пс": 50}, xp_x, unspent_xp=1232085430),
    create_player("Мс Акерман", {"Вн": 40, "Сл": 50, "Тч": 50}, xp_x, unspent_xp=1395707935),
    create_player("Макаквел", {"Вн": 40, "Сл": 50, "Тч": 50}, xp_x, unspent_xp=1215740470),
    create_player("Макакер ", {"Вн": 40, "Сл": 50, "Тч": 50}, xp_x, unspent_xp=1368078427)
]

rows = [player.summary_row() for player in players]

print(f"{'Имя':<12} {'Распределённый':>20} {'Нераспр.':>15} {'Всего':>15} {'Осталось':>15}")
print("-" * 80)
for row in rows:
    print(f"{row['Имя']:<12} {row['Распределённый опыт']:>20,} {row['Нераспределённый опыт']:>15,} {row['Всего опыта']:>15,} {row['Осталось до макс.']:>15,}")  

def main():
    st.title("Калькулятор опыта игрока")
    name = st.text_input("Фамилия/Имя игрока")
    
    # Ввод уровней по каждому стату
    levels = {}
    st.header("Уровни характеристик")
    for stat in default_levels:
        levels[stat] = st.number_input(f"{stat}", min_value=2, max_value=60, value=default_levels[stat])
    unspent_xp = st.number_input("Нераспределённый опыт", min_value=0, value=0)
    
    if st.button("Рассчитать"):
        player = Player(name, levels, xp_x, unspent_xp)
        player.summary()
        st.write(player.summary_row())

if __name__ == "__main__":
    main()
