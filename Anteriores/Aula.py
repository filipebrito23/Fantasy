import gspread

gc = gspread.service_account(filename="service_account.json")
ws = gc.open_by_key("1IiJb0iJW4Vnqyh5CFs8jZOSSZqlmdBGbWJCPFoNO4ao").worksheet("CHA x KDG")


dados = [
    ["A1", "B1", "C1", "D1", "E1"],
    ["A2", "B2", "C2", "D2", "E2"],
    ["A3", "B3", "C3", "D3", "E3"],
    ["A4", "B4", "C4", "D4", "E4"],
    ["A5", "B5", "C5", "D5", "E5"],
]

ws.update(dados,"E2:I6")