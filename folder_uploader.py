import os
import re
import datetime
import psycopg2
from typing import Optional
import streamlit as st
from supabase import Client

def get_db_connection():
    try:
        return psycopg2.connect(
            host=st.secrets["host"],
            dbname=st.secrets["dbname"],
            user=st.secrets["user"],
            password=st.secrets["password"],
            port=st.secrets["port"]
        )
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        return None

def upload_file_to_storage(local_path: str, storage_path: str, supabase: Client) -> Optional[str]:
    try:
        bucket_name = st.secrets["storage_bucket"]
        with open(local_path, "rb") as f:
            supabase.storage.from_(bucket_name).upload(storage_path, f)
        return supabase.storage.from_(bucket_name).get_public_url(storage_path)
    except Exception:
        return None  # silently fail duplicate uploads

def extract_animal_id(filepath: str) -> Optional[str]:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if match := re.search(r"Animal ID[,\s:]+([A-Za-z0-9]+)", line, re.IGNORECASE):
                    return match.group(1).strip()
        return None
    except Exception:
        return None

def extract_date(folder_name: str) -> Optional[datetime.date]:
    clean = re.sub(r"\D", "", folder_name)
    try:
        return datetime.datetime.strptime(clean[:8], "%m%d%Y").date()
    except Exception:
        return None

def infer_folder_type(name: str) -> str:
    lname = name.lower()
    if "protocol" in lname:
        return "protocol"
    elif "test" in lname:
        return "test"
    else:
        return "train"

def process_folder(root_path: str, supabase: Client, uploader: str, experiment_description: str) -> bool:
    conn = get_db_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()

        # Insert experiment
        experiment_name = os.path.basename(root_path)
        cur.execute("""
            INSERT INTO experiments (experiment_name, description)
            VALUES (%s, %s)
            ON CONFLICT (experiment_name) DO UPDATE SET description = EXCLUDED.description
            RETURNING experiment_id
        """, (experiment_name, experiment_description))
        experiment_id = cur.fetchone()[0]

        for rig_name in os.listdir(root_path):
            rig_path = os.path.join(root_path, rig_name)
            if not os.path.isdir(rig_path):
                continue

            cur.execute("""
                INSERT INTO rigs (experiment_id, rig_name)
                VALUES (%s, %s)
                ON CONFLICT (experiment_id, rig_name) DO NOTHING
                RETURNING rig_id
            """, (experiment_id, rig_name))
            rig_id = cur.fetchone()[0] if cur.rowcount else cur.execute("SELECT rig_id FROM rigs WHERE experiment_id = %s AND rig_name = %s", (experiment_id, rig_name)) or cur.fetchone()[0]

            for group_name in os.listdir(rig_path):
                group_path = os.path.join(rig_path, group_name)
                if not os.path.isdir(group_path):
                    continue

                cur.execute("""
                    INSERT INTO exp_groups (rig_id, group_name)
                    VALUES (%s, %s)
                    ON CONFLICT (rig_id, group_name) DO NOTHING
                    RETURNING group_id
                """, (rig_id, group_name))
                group_id = cur.fetchone()[0] if cur.rowcount else cur.execute("SELECT group_id FROM exp_groups WHERE rig_id = %s AND group_name = %s", (rig_id, group_name)) or cur.fetchone()[0]

                for folder_name in os.listdir(group_path):
                    folder_path = os.path.join(group_path, folder_name)
                    if not os.path.isdir(folder_path):
                        continue

                    folder_type = infer_folder_type(folder_name)

                    cur.execute("""
                        INSERT INTO training_folders (group_id, folder_name, folder_type)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (group_id, folder_name) DO NOTHING
                        RETURNING folder_id
                    """, (group_id, folder_name, folder_type))
                    folder_id = cur.fetchone()[0] if cur.rowcount else cur.execute("SELECT folder_id FROM training_folders WHERE group_id = %s AND folder_name = %s", (group_id, folder_name)) or cur.fetchone()[0]

                    session_folders = sorted(
                        [d for d in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, d))],
                        key=lambda x: extract_date(x) or datetime.date.min
                    )

                    for session_folder in session_folders:
                        session_date = extract_date(session_folder)
                        if not session_date:
                            continue
                        session_path = os.path.join(folder_path, session_folder)

                        cur.execute("""
                            INSERT INTO days (folder_id, day_number, session_date, day_label)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (folder_id, session_date) DO NOTHING
                            RETURNING day_id
                        """, (folder_id, session_folders.index(session_folder)+1, session_date, session_folder))
                        day_id = cur.fetchone()[0] if cur.rowcount else cur.execute("SELECT day_id FROM days WHERE folder_id = %s AND session_date = %s", (folder_id, session_date)) or cur.fetchone()[0]

                        for file in os.listdir(session_path):
                            ext = os.path.splitext(file)[1].lower()
                            if ext not in ['.txt', '.pro', '.ms8']:
                                continue
                            file_path = os.path.join(session_path, file)
                            animal_id = extract_animal_id(file_path)
                            if not animal_id:
                                continue

                            # Insert mouse
                            cur.execute("""
                                INSERT INTO mice (mouse_id, group_id)
                                VALUES (%s, %s)
                                ON CONFLICT (mouse_id) DO NOTHING
                            """, (animal_id, group_id))

                            # Upload file
                            storage_path = f"{experiment_name}/{rig_name}/{group_name}/{folder_name}/{session_folder}/{file}"
                            url = upload_file_to_storage(file_path, storage_path, supabase)

                            # Insert file
                            if url:
                                cur.execute("""
                                    INSERT INTO files (day_id, original_name, mouse_id, uploader, file_url)
                                    VALUES (%s, %s, %s, %s, %s)
                                    ON CONFLICT (day_id, original_name) DO NOTHING
                                """, (day_id, file, animal_id, uploader, url))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Processing failed: {str(e)}")
        return False
    finally:
        conn.close()
