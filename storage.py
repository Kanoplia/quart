import sqlite3

# Устанавливаем соединение с базой данных
connection = sqlite3.connect('my_database.db')
cursor = connection.cursor()

# Создаем таблицу Users
cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
id INTEGER,
balanse INTEGER DEFAULT 1000,
win INTEGER DEFAULT 0,
lose INTEGER DEFAULT 0,
winstreak INTEGER DEFAULT 0,
dsp INTEGER DEFAULT 0
)
''')

# Сохраняем изменения и закрываем соединение
connection.commit()
connection.close()