import sqlite3

# Устанавливаем соединение с базой данных
connection = sqlite3.connect('my_database.db')
cursor = connection.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS Users (
    id INTEGER PRIMARY KEY,
    status INTEGER DEFAULT 10
)
''')


cursor.execute('''
CREATE TABLE IF NOT EXISTS Tickets (
    id INTEGER PRIMARY KEY,
    teg TEXT NOT NULL,
    tiket TEXT,
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
)
''')

# Сохраняем изменения и закрываем соединение
connection.commit()
connection.close()