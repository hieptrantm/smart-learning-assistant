import os
from typing import Any, Dict, List, Sequence
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DB_USER = os.getenv("POSTGRES_USER", "")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
DB_NAME = os.getenv("POSTGRES_DB", "")
DB_HOST = os.getenv("POSTGRES_HOST", "")
DB_PORT = os.getenv("POSTGRES_PORT", "")
DB_SCHEMA = os.getenv("POSTGRES_SCHEMA", "")

def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        # options=f"-c search_path={DB_SCHEMA}",
        cursor_factory=RealDictCursor
    )

def add_message(subject_id, user_id, content, role='user'):
    created_at = datetime.utcnow()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO subject_messages (subject_id, user_id, content, role, created_at) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (subject_id, user_id, content, role, created_at)
    )
    result = cur.fetchone()
    message_id = result['id'] if result else None
    conn.commit()
    cur.close()
    conn.close()
    return message_id

def delete_messages_by_subject_id_and_message_ids(subject_id, message_ids):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM subject_messages WHERE subject_id = %s AND id = ANY(%s)",
        (subject_id, message_ids)
    )
    deleted_count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return deleted_count

def get_messages(subject_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM subject_messages WHERE subject_id = %s ORDER BY created_at ASC",
        (subject_id,)
    )
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return messages

def get_messages_by_role(subject_id, role=None):
    conn = get_connection()
    cur = conn.cursor()
    if role:
        cur.execute(
            "SELECT * FROM subject_messages WHERE subject_id = %s AND role = %s ORDER BY created_at ASC",
            (subject_id, role)
        )
    else:
        cur.execute(
            "SELECT * FROM subject_messages WHERE subject_id = %s ORDER BY created_at ASC",
            (subject_id,)
        )
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return messages

def get_conversations_by_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM conversations WHERE user_id = %s ORDER BY id DESC",
        (user_id,)
    )
    conversations = cur.fetchall()
    cur.close()
    conn.close()
    return conversations

def get_conversation_by_user_and_id(user_id, conversation_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM conversations WHERE user_id = %s AND id = %s ",
        (user_id, conversation_id)
    )
    conversation = cur.fetchone()
    cur.close()
    conn.close()
    return conversation

def delete_conversation_by_user_and_id(user_id, conversation_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM conversations WHERE user_id = %s AND id = %s",
        (user_id, conversation_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return True

def insert_sft_data(rows: List[Dict[str, Any]]):
    conn = get_connection()
    cur = conn.cursor()
    if not rows:
        return 0
    COLUMNS: Sequence[str] = (
        "session_id",
        "system_prompt",
        "message",
        "qa_prompt",
        "response",
        "step",
    )

    values = [
        tuple(row.get(col) for col in COLUMNS)
        for row in rows
    ]

    sql = f"""
        INSERT INTO sft_data ({", ".join(COLUMNS)})
        VALUES %s
        RETURNING id;
    """
    execute_values(cur, sql, values)
    inserted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return inserted

# Test connection
if __name__ == "__main__":
    try:
        conn = get_connection()
        print("Database connection successful!")
        conn.close()
    except Exception as e:
        print(f"Database connection failed: {e}")
        
    # # Print all tables in the current schema
    # try:
    #     conn = get_connection()
    #     cur = conn.cursor()
    #     cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (DB_SCHEMA,))
    #     tables = cur.fetchall()
    #     print(f"Tables in schema '{DB_SCHEMA}': {[table['table_name'] for table in tables]}")
    #     cur.close()
    #     conn.close()
    # except Exception as e:
    #     print(f"Failed to fetch tables: {e}")
        
    # Print all data in Users table
    try:
        # create_conversation(user_id=1, name="Test Conversation")
        # conn = get_connection()
        # cur = conn.cursor()
        
        # Create messages for testing
        # add_message(subject_id=1, content="Yes, of course", created_by=1, role='assistant')
        delete_messages_by_subject_id_and_message_ids(subject_id=1, message_ids=[4, 5])
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM \"subject_messages\"")
        messages = cur.fetchall()
        print(f"Data in Subject Messages table: {messages}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Failed to fetch data from Subject Messages table: {e}")