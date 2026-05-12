import os
import re
from typing import Any, Dict, List, Optional, Sequence
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

CHUNK_ID_PATTERN = re.compile(r"^(.*?_chunk_)(\d+)$", re.IGNORECASE)

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


def _parse_chunk_checkpoint(checkpoint_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not checkpoint_id:
        return None
    raw = str(checkpoint_id).strip()
    match = CHUNK_ID_PATTERN.match(raw)
    if not match:
        return None
    prefix, number_str = match.groups()
    return {
        "prefix": prefix,
        "number": int(number_str),
        "width": len(number_str),
    }


def _build_chunk_window(current_checkpoint: str, previous_checkpoint: Optional[str]) -> List[str]:
    current_parsed = _parse_chunk_checkpoint(current_checkpoint)
    if not current_parsed:
        return [current_checkpoint]

    start_num = 1
    width = max(2, current_parsed["width"])
    previous_parsed = _parse_chunk_checkpoint(previous_checkpoint)
    if previous_parsed and previous_parsed["prefix"] == current_parsed["prefix"]:
        start_num = previous_parsed["number"] + 1
        width = max(width, previous_parsed["width"])

    if start_num > current_parsed["number"]:
        start_num = current_parsed["number"]

    prefix = current_parsed["prefix"]
    return [f"{prefix}{idx:0{width}d}" for idx in range(start_num, current_parsed["number"] + 1)]


def get_session_chunk_window(
    subject_id: int,
    current_session_id: Optional[int] = None,
    current_checkpoint_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolve chunk window for Q&A retrieval:
    - End at current session checkpoint_node_id
    - Start right after nearest previous passed session checkpoint_node_id
    - If no previous passed session, start from *_chunk_01
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        current_session = None
        if current_checkpoint_node_id:
            cur.execute(
                """
                SELECT id, checkpoint_node_id, session_date, start_time
                FROM study_sessions
                WHERE subject_id = %s AND checkpoint_node_id = %s
                ORDER BY session_date ASC NULLS LAST, start_time ASC NULLS LAST, id ASC
                LIMIT 1
                """,
                (subject_id, current_checkpoint_node_id),
            )
            current_session = cur.fetchone()
        elif current_session_id is not None:
            cur.execute(
                """
                SELECT id, checkpoint_node_id, session_date, start_time
                FROM study_sessions
                WHERE subject_id = %s AND id = %s
                LIMIT 1
                """,
                (subject_id, current_session_id),
            )
            current_session = cur.fetchone()
        else:
            # Fallback when FE does not pass current session id.
            cur.execute(
                """
                                SELECT id, checkpoint_node_id, session_date, start_time
                FROM study_sessions
                WHERE subject_id = %s
                  AND checkpoint_node_id IS NOT NULL
                ORDER BY
                  CASE WHEN learning_status IN ('not_started', 'in_progress') THEN 0 ELSE 1 END,
                  session_date ASC NULLS LAST,
                  start_time ASC NULLS LAST,
                  id ASC
                LIMIT 1
                """,
                (subject_id,),
            )
            current_session = cur.fetchone()

        if not current_session or not current_session.get("checkpoint_node_id"):
            return {
                "current_session_id": current_session_id,
                "current_checkpoint": current_checkpoint_node_id,
                "previous_passed_checkpoint": None,
                "chunk_ids": [],
            }

        resolved_session_id = current_session["id"]
        current_checkpoint = current_session["checkpoint_node_id"]
        current_session_date = current_session.get("session_date")
        current_start_time = current_session.get("start_time")

        if current_session_date is not None and current_start_time is not None:
            cur.execute(
                """
                SELECT checkpoint_node_id
                FROM study_sessions
                WHERE subject_id = %s
                  AND learning_status = 'passed'
                  AND checkpoint_node_id IS NOT NULL
                  AND (
                    session_date < %s
                    OR (session_date = %s AND start_time < %s)
                    OR (session_date = %s AND start_time = %s AND id < %s)
                  )
                ORDER BY session_date DESC NULLS LAST, start_time DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (
                    subject_id,
                    current_session_date,
                    current_session_date,
                    current_start_time,
                    current_session_date,
                    current_start_time,
                    resolved_session_id,
                ),
            )
        else:
            cur.execute(
                """
                SELECT checkpoint_node_id
                FROM study_sessions
                WHERE subject_id = %s
                  AND id < %s
                  AND learning_status = 'passed'
                  AND checkpoint_node_id IS NOT NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (subject_id, resolved_session_id),
            )
        previous_session = cur.fetchone()
        previous_checkpoint = previous_session["checkpoint_node_id"] if previous_session else None

        return {
            "current_session_id": resolved_session_id,
            "current_checkpoint": current_checkpoint,
            "previous_passed_checkpoint": previous_checkpoint,
            "chunk_ids": _build_chunk_window(current_checkpoint, previous_checkpoint),
        }
    finally:
        cur.close()
        conn.close()

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