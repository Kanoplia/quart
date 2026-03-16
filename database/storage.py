import sqlite3
import logging

logger = logging.getLogger(__name__)

def init_db():
    """Инициализация базы данных с необходимыми таблицами и колонками"""
    try:
        conn = sqlite3.connect('my_database.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER,
                role_name TEXT,
                chat_id INTEGER,
                PRIMARY KEY (user_id, chat_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voting_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_type TEXT,
                target_date TEXT,
                duration_hours INTEGER,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                roles_config TEXT -- JSON строка с конфигурацией ролей
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                voter_id INTEGER,
                candidate_id INTEGER,
                role_type TEXT,
                FOREIGN KEY (session_id) REFERENCES voting_sessions (id)
            )
        ''')
        
        # Создание таблицы Tickets
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Tickets (
            id INTEGER PRIMARY KEY,
            teg TEXT NOT NULL,
            tiket TEXT,
            user_id INTEGER,
            topic_id INTEGER,
            is_closed INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
        ''')
        
        # Проверка наличия необходимых колонок
        cursor.execute("PRAGMA table_info(Tickets)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if 'topic_id' not in columns:
            cursor.execute("ALTER TABLE Tickets ADD COLUMN topic_id INTEGER")
            logger.info("Added 'topic_id' column to Tickets table")
            
        if 'is_closed' not in columns:
            cursor.execute("ALTER TABLE Tickets ADD COLUMN is_closed INTEGER DEFAULT 0")
            logger.info("Added 'is_closed' column to Tickets table")
        
        conn.commit()
        conn.close()
        
        logger.info("Database initialized successfully")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
        return False
    finally:
        if conn:
            conn.close()