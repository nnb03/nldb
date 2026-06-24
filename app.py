from ollama import chat
from db import get_connection
from build_rag import build_rag

from rag import (
    retrieve_context,
    table_exists,
    get_all_tables
)

import chromadb


# -----------------------------
# RAG Initialization
# -----------------------------

client = chromadb.PersistentClient(
    path="./rag_db"
)

try:

    collection = client.get_collection(
        "schema"
    )

    data = collection.get()

    if len(data["ids"]) == 0:

        print("Building RAG...")

        build_rag()

except:

    print("Creating RAG...")

    build_rag()


# -----------------------------
# PostgreSQL
# -----------------------------

conn = get_connection()

cursor = conn.cursor()


# -----------------------------
# Helpers
# -----------------------------

def validate_sql(sql):

    sql_upper = sql.upper()

    blocked = [
        "DROP DATABASE",
        "TRUNCATE"
    ]

    for item in blocked:

        if item in sql_upper:

            return False, item

    if sql_upper.startswith("DELETE"):

        if "WHERE" not in sql_upper:

            return False, "DELETE WITHOUT WHERE"

    return True, "OK"


def extract_table_name(question):

    words = question.lower().split()

    for i, word in enumerate(words):

        if word == "table":

            if i + 1 < len(words):

                return words[i + 1]

    return None


# -----------------------------
# Main Loop
# -----------------------------

print("=" * 60)
print("AI DATABASE ASSISTANT")
print("=" * 60)

while True:

    question = input("\nYou: ")

    if question.lower() == "exit":

        break

    # -----------------------------
    # CREATE TABLE PRE-CHECK
    # -----------------------------

    if (
        "create" in question.lower()
        and "table" in question.lower()
    ):

        table_name = extract_table_name(
            question
        )

        if table_name:

            if table_exists(table_name):

                print(
                    f"\nTable '{table_name}' already exists."
                )

                continue

    # -----------------------------
    # RAG Retrieval
    # -----------------------------

    context = retrieve_context(
        question
    )

    all_tables = get_all_tables()

    tables_text = "\n".join(
        all_tables
    )

    # -----------------------------
    # Prompt
    # -----------------------------

    prompt = f"""
Database Context:

{context}

Existing Tables:

{tables_text}

You are a PostgreSQL Expert.

Rules:

1. Generate VALID PostgreSQL SQL.
2. Return ONLY SQL.
3. No markdown.
4. No explanation.
5. Never create existing tables.
6. Every CREATE TABLE must contain:
   id SERIAL PRIMARY KEY
7. Never generate incomplete SQL.
8. Generate executable PostgreSQL.
9. If user creates a table without columns,
   generate reasonable columns.

User Request:

{question}
"""

    print(
        "\nLlama Generating SQL...\n"
    )

    response = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        stream=True
    )

    sql = ""

    for chunk in response:

        token = chunk["message"]["content"]

        print(
            token,
            end="",
            flush=True
        )

        sql += token

    print()

    sql = sql.replace(
        "```sql",
        ""
    )

    sql = sql.replace(
        "```",
        ""
    )

    sql = sql.strip()

    # -----------------------------
    # SQL Validation
    # -----------------------------

    valid, message = validate_sql(
        sql
    )

    if not valid:

        print(
            f"\nBlocked: {message}"
        )

        continue

    # -----------------------------
    # DROP TABLE CONFIRMATION
    # -----------------------------

    if sql.upper().startswith(
        "DROP TABLE"
    ):

        confirm = input(
            "\nWARNING: Table will be deleted.\nType YES to continue: "
        )

        if (
            confirm
            .strip()
            .upper()
            != "YES"
        ):

            print(
                "Operation Cancelled"
            )

            continue

    # -----------------------------
    # Execute SQL
    # -----------------------------

    try:

        cursor.execute(sql)

        if sql.upper().startswith(
            "SELECT"
        ):

            rows = cursor.fetchall()

            print(
                "\nResults"
            )

            print(
                "-" * 60
            )

            for row in rows:

                print(row)

        else:

            conn.commit()

            print(
                "\nQuery Executed Successfully"
            )

            # Update RAG only when schema changes

            ddl = [
                "CREATE TABLE",
                "ALTER TABLE",
                "DROP TABLE"
            ]

            for command in ddl:

                if sql.upper().startswith(
                    command
                ):

                    print(
                        "\nUpdating RAG..."
                    )

                    build_rag()

                    print(
                        "RAG Updated"
                    )

                    break

    except Exception as e:

        conn.rollback()

        print(
            "\nDatabase Error:"
        )

        print(e)

cursor.close()
conn.close()