import chromadb
from db import get_connection

client = chromadb.PersistentClient(
    path="./rag_db"
)

collection = client.get_or_create_collection(
    "schema"
)


def build_rag():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema='public'
    """)

    tables = cursor.fetchall()

    existing_ids = set(
        collection.get()["ids"]
    )

    current_ids = set()

    for table in tables:

        table_name = table[0]

        current_ids.add(
            table_name
        )

        cursor.execute("""
        SELECT column_name,data_type
        FROM information_schema.columns
        WHERE table_name=%s
        ORDER BY ordinal_position
        """, (table_name,))

        columns = cursor.fetchall()

        doc = f"""
Table: {table_name}

Columns:
"""

        for col in columns:

            doc += f"""
{col[0]} ({col[1]})
"""

        collection.upsert(
            ids=[table_name],
            documents=[doc]
        )

    # Remove deleted tables from RAG

    removed_tables = existing_ids - current_ids

    if removed_tables:

        collection.delete(
            ids=list(removed_tables)
        )

    cursor.close()
    conn.close()


if __name__ == "__main__":

    build_rag()

    print("RAG Built")