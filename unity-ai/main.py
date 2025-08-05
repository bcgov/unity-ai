import dotenv
import os
import sys
import datetime as dt
from flask import Flask, request, abort
import time
import jwt
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_postgres import PGVector
import json, requests
from flask_cors import CORS
import asyncio
import aiohttp
import os
import re
import hashlib, json
from collections import Counter
import tiktoken
from typing import Optional, Dict, Any
import psycopg
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

dotenv.load_dotenv()

# Flask environment configuration
FLASK_ENV = os.getenv("FLASK_ENV", "development")

# Configure Flask based on environment
if FLASK_ENV == "production":
    app.config['DEBUG'] = False
    app.config['TESTING'] = False
else:
    # Default to development settings for any non-production environment
    app.config['DEBUG'] = True
    app.config['TESTING'] = False

headers = {"x-api-key": os.getenv("METABASE_KEY")}

EMBED_WORKSHEETS = False
EMBED_SAMPLES = True
K = 7
MODEL="gpt-4o-mini"

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "unity_ai")
DB_USER = os.getenv("DB_USER", "unity_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "unity_pass")

# Construct DATABASE_URL from individual components
DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

SQL_BLOCK_RE = re.compile(r"```sql\s*(.+?)```", re.I | re.S)
_meta_re = re.compile(
    r"""\#\#\#\s*Metadata:\s*           # header
        (?:```json\s*)?              # optional ```json fence
        (\{.*?})                     # capture {...}
        (?:\s*```)?                  # optional closing fence
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)

enc = tiktoken.encoding_for_model("gpt-4o-mini")   # same tokeniser

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

# Initialize PostgreSQL vector store
vector_store = PGVector(
    embeddings=embedding_model,
    collection_name="embedded_schema",
    connection=DATABASE_URL,
    use_jsonb=True,
)

# Database connection for app data
def get_db_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

# Initialize chat table
def init_chat_table():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    conversation JSONB NOT NULL,
                    tenant_id TEXT,
                    metabase_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id);
                CREATE INDEX IF NOT EXISTS idx_chats_tenant_id ON chats(tenant_id);
            """)
            conn.commit()

# Initialize chat table on startup
init_chat_table()

def get_sql(sql, db_id, metabase_url):
    ds_req = {
        "database": db_id,
        "type": "native",
        "native": {"query": sql},
    }
    r = requests.post(
        f"{metabase_url}/api/dataset",
        headers=headers,
        json=ds_req,
    )
    r.raise_for_status()
    return r.json()["data"]

def extract_sql(text: str) -> str | None:
    # Try code fence first
    m = SQL_BLOCK_RE.search(text)
    if m:
        return m.group(1).strip()
    # Fallback: look for '### SQL:' header
    sql_header = re.search(r"### SQL:\s*([\s\S]+?)(?:\n###|\Z)", text)
    if sql_header:
        return sql_header.group(1).strip()
    return None

def run_and_fingerprint(sql: str, db_id, metabase_url) -> tuple[str, tuple[str, ...], str]:
    """
    Returns (row_count, col_name_tuple, digest_of_first_5_rows)
    """
    data  = get_sql(sql, db_id, metabase_url)
    rows  = data["rows"]
    cols  = tuple(                               # ← tuple, not list
        c["name"] if isinstance(c, dict) else c
        for c in data["cols"]
    )
    head  = rows[:5]
    digest = hashlib.md5(json.dumps(head, default=str).encode()).hexdigest()
    return str(len(rows)), cols, digest

def majority(items: list):
    if not items:
        return None
    counts = Counter(items)
    winner, freq = counts.most_common(1)[0]
    return winner if freq > 1 else None   

async def fetch_chat_completion(input, model, session, index):
    print("tokens:", len(enc.encode(input)))
    url = os.getenv("COMPLETION_ENDPOINT")
    headers = {
        "Authorization": f"Bearer {os.getenv('COMPLETION_KEY')}",
        "Content-Type": "application/json"
    }
    json_data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": input}
        ],
        "temperature": 0.2
    }

    async with session.post(url, headers=headers, json=json_data) as response:
        if response.status != 200:
            print(f"[{index}] Error: {response.status}")
            print(await response.text())
            return None
        data = await response.json()
        print("Tokens used:", data["usage"]["total_tokens"])
        # print(data["choices"][0]["message"]["content"])
        return data["choices"][0]["message"]["content"]

def get_table_schemas():
    schema = requests.get(
        f"{os.getenv('MB_EMBED_URL')}/api/database/{os.getenv('MB_EMBED_ID')}/metadata",
        headers=headers
    ).json()

    junk_cols = {
        "CreatorId", "LastModificationTime", "LastModifierId",
        "ExtraProperties", "ConcurrencyStamp", "CreationTime",
    }
    junk_tables = {"ApplicationFormSubmissions", "__EFMigrationsHistory"}

    docs = []

    for tbl in schema["tables"]:
        if tbl["schema"] != "public" or tbl["name"] in junk_tables:
            continue

        cols = [
            f"{c['name']} ({c['base_type']})"
            for c in tbl["fields"]
            if c["name"] not in junk_cols
        ]

        page = f"# {tbl['name']}({', '.join(cols)})"
        docs.append(page)
        print(page)

    return docs

def purge_embeddings():
    """Delete all existing embeddings from the vector store"""
    print("Purging existing embeddings...")
    try:
        # Use the same connection method as get_db_connection()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Delete all records from the langchain_pg_embedding table for our collection
                cur.execute("""
                    DELETE FROM langchain_pg_embedding 
                    WHERE collection_id IN (
                        SELECT uuid FROM langchain_pg_collection 
                        WHERE name = %s
                    )
                """, ("embedded_schema",))
                deleted_count = cur.rowcount
                conn.commit()
                print(f"Purged {deleted_count} existing embeddings")
    except Exception as e:
        print(f"Error purging embeddings: {e}")
        raise

def embed_schema():
    # First purge existing embeddings
    purge_embeddings()
    
    # Then add new embeddings
    print("Adding new embeddings...")
    vector_store.add_documents([Document(page_content=p.strip()) for p in get_table_schemas()])

    if EMBED_WORKSHEETS:
        vector_store.add_documents([Document(page_content=p.strip()) for p in get_parsed_worksheets()])

def sql_is_valid(sql: str, db_id: int, metabase_url) -> tuple[bool, str | None]:
    """
    Try to run `sql` against Metabase and tell whether it works.

    Returns
    -------
    (True, None)                  … query ran OK
    (False, "…message…")          … Metabase could not execute it
    """
    payload = {
        "database": db_id,
        "type":     "native",
        "native":   {"query": sql},
    }
    r = requests.post(f"{metabase_url}/api/dataset", headers=headers, json=payload)

    if r.status_code not in (200, 202):
        return False, f"HTTP {r.status_code}: {r.text}"

    body = r.json()
    if r.status_code == 202 and body.get("status") == "running":
        job_id = body["id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            jr = requests.get(f"{metabase_url}/api/async/{job_id}", headers=headers)
            if jr.status_code == 200:
                body = jr.json()
                break
            time.sleep(0.5)
    if "error" in body:
        return False, body["error"]

    return True, None

def extract_metadata(block: str) -> Optional[Dict[str, Any]]:
    """
    Returns the dict that follows a “### Metadata:” header, tolerating:
      • bare Python‐style dict  {'key': 'val'}
      • valid JSON              {"key": "val"}
      • either wrapped (```json … ```) or bare

    None is returned if nothing parses cleanly.
    """
    m = _meta_re.search(block)
    if not m:
        return None

    raw = m.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    return None

async def nl_to_sql(question, past_questions, db_id, metabase_url):  

    retrieved = vector_store.similarity_search(question, k=5)
    retrieved_tables = "\n".join(doc.page_content for doc in retrieved)

    with open("QDECOMP_examples.json", "r") as file:
        examples = json.load(file)
    newline = '\n'
    examples = [f"### Schema:{newline}{newline.join(ex['Schema'])}{newline}### Question:{newline}{ex['Question']}{newline}### Reasoning:{newline}{ex['Reasoning']}{newline}### SQL:{newline}{ex['SQL']}{newline}### Metadata:{newline}{json.dumps({'title': ex['title'], 'x_axis': ex['x_axis'], 'y_axis': ex['y_axis'], 'visualization_options': ex['visualization_options']})}" for ex in examples]
    past_question_string = f'Note that the previous question in this conversation was: "{past_questions[-2]["question"]}" and the generated SQL was: "{past_questions[-2]["SQL"]}. "' if len(past_questions) > 1 else ""
    prompt = f"{f'{newline}{newline}'.join(examples)}{newline}{newline}### Schema:{newline}{retrieved_tables}{newline}### Question:{newline}The current date is {dt.datetime.now().strftime('%Y-%m-%d')}. {past_question_string}Please generate sql and metadata for the following question, with reasoning but no explanation. Please enable map option only for questions involving regional districts: {question}{newline}### Reasoning:"

    print(prompt)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_chat_completion(prompt, MODEL, session, i) for i in range(K)]
        completions = await asyncio.gather(*tasks)
    # completions = [get_stream(prompt, MODEL)]
    print(completions)

    candidates = []
    for raw in completions:
        if not raw:
            continue
        sql = extract_sql(raw)
        if not sql:
            print("No SQL found in completion:", raw)
            continue

        metadata = extract_metadata(raw)
        if not metadata:
            print("No metadata found in completion:", raw)
            continue

        ok, _ = sql_is_valid(sql, db_id, metabase_url)
        if not ok:
            print("SQL is not valid:", sql)
            continue

        try:
            fp = run_and_fingerprint(sql, db_id, metabase_url)
            if not fp:
                print("No fingerprint returned for SQL:", sql)
                continue
            candidates.append((fp, sql, metadata))
        except Exception as e:
            print("Exec error", e)
            continue

    # -------- majority vote on fingerprints --------
    fingerprints = [fp for fp, _, _ in candidates]
    winner_fp = majority(fingerprints)

    if winner_fp:
        for fp, sql, metadata in candidates:
            if fp == winner_fp:
                print("returning sql, metadata:", sql, metadata)
                return sql, metadata
    # ---------- fallback ----------
    if candidates:
        print("returning Candidate:", candidates[0][1])
        return candidates[0][1], candidates[0][2]
    else:
        print("raw candidates:", completions)
        print("parsed candidates:", candidates)

def create_question(sql: str, db_id: int, collection_id: int, name: str, metabase_url) -> int:
    r = requests.post(f"{metabase_url}/api/card", headers=headers, json={
        "name": name,
        "visualization_settings": {},
        "collection_id": collection_id,
        "enable_embedding": True,
        "dataset_query": {
            "database": db_id,
            "native": {"query": sql},
            "type": "native"
        },
        "display": "table"
    })
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}: {r.text}")

    card_id = r.json()["id"]
    r2 = requests.put(f"{metabase_url}/api/card/{card_id}",
                      headers=headers,
                      json={"enable_embedding": True})
    if r2.status_code != 200:
        raise Exception(f"HTTP {r2.status_code}: {r2.text}")

    return card_id

def get_all_card_ids(metabase_url) -> list:
    """Get all card IDs from Metabase"""
    try:
        r = requests.get(f"{metabase_url}/api/card", headers=headers)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}: {r.text}")
        
        cards = r.json()
        return [card["id"] for card in cards]
    except Exception as e:
        print(f"Error getting cards from Metabase: {e}")
        return []

def update_card_visualization(card_id: int, mode: str, x_field: list, y_field: list, metabase_url: str) -> None:
    """Update a Metabase card's visualization settings"""
    r = requests.put(f"{metabase_url}/api/card/{card_id}",
        headers=headers,
        json={"display": mode,
            "visualization_settings": {
                "graph.dimensions": x_field,
                "graph.metrics": y_field,
                "pie.dimension": x_field,
                "pie.metric": y_field[0] if len(y_field) > 0 else "",
                "map.region": "1c5d50ee-4389-4593-37c1-fa8d4687ff4c"
            }
        })
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}: {r.text}")

def generate_embed_url(card_id: int, metabase_url) -> str:
    payload = {
        "resource": {"question": card_id},
        "params":   {}
    }
    token = jwt.encode(payload, os.getenv("MB_EMBED_SECRET"), algorithm="HS256")
    return f"{metabase_url}/embed/question/{token}?bordered=true&titled=false"

@app.route("/api/change_display", methods=["POST"])
def change_display():
    if request.method == "POST":
        data = request.get_json()
        try:
            mode = data.get("mode")
            card_id = data.get("card_id")
            x_field = data.get("x_field") 
            y_field = data.get("y_field") 
            metabase_url = data.get("metabase_url")
            visualization_options = data.get("visualization_options")
        except:
            return abort(400, "Data is required")
        
        if card_id == None or mode == None or x_field == None or y_field == None:
            return abort(400, "Missing inputs")

        update_card_visualization(card_id, mode, x_field, y_field, metabase_url)
        embed_url = generate_embed_url(card_id, metabase_url)
        return {"url": embed_url, "card_id": card_id, "x_field": x_field, "y_field": y_field, "visualization_options": visualization_options}, 200
    return ""

@app.route("/api/delete", methods=["GET", "POST"])
def delete_question():
    data = request.get_json()
    try:
        card_id = data.get("card_id")
        metabase_url = data.get("metabase_url")
    except:
        return abort(400, "Data is required")
    
    r = requests.delete(f"{metabase_url}/api/card/{card_id}", headers=headers)
    if r.status_code != 200 and r.status_code != 204:
        return {"success": False}
    return {"success": True}

def get_db_and_collection_id(tenant_id):
    tenant_db_mapping = {
        "Cyrus Org": 3,
        "UnknownTenant": 3,  # Default for unknown tenants
        # Add more tenant mappings here as needed
    }
    return tenant_db_mapping.get(tenant_id, 3), 47 # TODO change back to -1 default

@app.route("/api/ask", methods=["GET", "POST"])
async def ask():
    if request.method == "POST":

        data = request.get_json()
        try:
            question = data.get("question") 
            conversation = data.get("conversation") 
            metabase_url = data.get("metabase_url")
            tenant_id = data.get("tenant_id")
            
            db_id, collection_id = get_db_and_collection_id(tenant_id)

        except:
            return abort(400, "Data is required")
        
        print(f"Request details - Tenant: {tenant_id}, DB ID: {db_id}, Collection: {collection_id}, Metabase URL: {metabase_url}")
        
        if None in (metabase_url, collection_id) or db_id == -1:
            print(f"Authorization failed - Missing: metabase_url={metabase_url}, db_id={db_id}, collection_id={collection_id}")
            time.sleep(1)
            return abort(401, "Authorization required")
        
        past_questions = [{"question": c["question"], "SQL": c["embed"]["SQL"]} for c in conversation]

        if question == "How many applications were approved in each subsector?":
            sql = '''SELECT COALESCE(applicants."SubSector", 'Unspecified') AS SubSector, 
COUNT(*) AS TotalApplications
FROM "public"."Applications" AS applications
JOIN "public"."Applicants" AS applicants ON applications."ApplicantId" = applicants."Id"
WHERE applicants."SubSector" IS NOT NULL 
AND applicants."SubSector" != '' 
AND LOWER(applicants."SubSector") != 'other'
GROUP BY applicants."SubSector"
ORDER BY TotalApplications DESC 
LIMIT 15; 
            '''
            metadata = {
                "title": "Approved Applications Per Subsector",
                "x_axis": ['SubSector'],
                "y_axis": ['TotalApplications'],
                "visualization_options": ["bar", "pie"]
            }
            time.sleep(3)
        elif question == "Total applications and distributed funding per month in 2024":
            sql = '''SELECT 
    EXTRACT(MONTH FROM applications."SubmissionDate") AS month, 
    COUNT(DISTINCT applicants."Id") AS total_applicants, 
    SUM(applications."ApprovedAmount") AS total_approved_funding
FROM 
    "public"."Applications" AS applications
JOIN 
    "public"."Applicants" AS applicants ON applications."ApplicantId" = applicants."Id"
WHERE 
    EXTRACT(MONTH FROM applications."SubmissionDate") IS NOT NULL
GROUP BY 
    month;'''
            metadata = {
                "title": "Total Applicants and Approved Funding Per Month in 2024",
                "x_axis": ["month"],
                "y_axis": ["total_applicants", "total_approved_funding"],
                "visualization_options": ["bar", "line"]
            }
            time.sleep(3)

        elif question == "Distribution of funding by regional district":
            sql = '''SELECT "public"."Applications"."RegionalDistrict" AS "RegionalDistrict",
SUM("public"."Applications"."ApprovedAmount") AS "sum"
FROM
"public"."Applications"

LEFT JOIN "public"."ApplicationStatuses" AS "ApplicationStatuses - ApplicationStatusId" ON "public"."Applications"."ApplicationStatusId" = "ApplicationStatuses - ApplicationStatusId"."Id"
WHERE
"ApplicationStatuses - ApplicationStatusId"."ExternalStatus" = 'Approved'
AND
"public"."Applications"."RegionalDistrict" IS NOT NULL
AND
"public"."Applications"."RegionalDistrict" != '' 
GROUP BY
"public"."Applications"."RegionalDistrict"
ORDER BY
"public"."Applications"."RegionalDistrict" ASC
            '''
            metadata = {
                "title": "Approved Amount per Regional District",
                "x_axis": ["RegionalDistrict"],
                "y_axis": ["sum"],
                "visualization_options": ["bar", "pie", "map"]
            }
            time.sleep(3)

        elif question == "Only 2024 Q3":
            sql = '''SELECT "public"."Applications"."RegionalDistrict" AS "RegionalDistrict",
SUM("public"."Applications"."ApprovedAmount") AS "sum"
FROM
"public"."Applications"

LEFT JOIN "public"."ApplicationStatuses" AS "ApplicationStatuses - ApplicationStatusId" ON "public"."Applications"."ApplicationStatusId" = "ApplicationStatuses - ApplicationStatusId"."Id"
WHERE
"ApplicationStatuses - ApplicationStatusId"."ExternalStatus" = 'Approved'
AND
"public"."Applications"."RegionalDistrict" IS NOT NULL
AND
"public"."Applications"."RegionalDistrict" != ''
AND "public"."Applications"."SubmissionDate" >= '2024-07-01'
AND "public"."Applications"."SubmissionDate" <= '2024-09-30'    
GROUP BY
"public"."Applications"."RegionalDistrict"
ORDER BY
"public"."Applications"."RegionalDistrict" ASC
            '''
            metadata = {
                "title": "Approved Amount per Regional District - 2024 Q3",
                "x_axis": ["RegionalDistrict"],
                "y_axis": ["sum"],
                "visualization_options": ["bar", "pie", "map"]
            }
            time.sleep(3)

        else:
        
            sql, metadata = await nl_to_sql(question, past_questions, db_id, metabase_url)
            if sql == "fail":
                return {"url": "fail", "card_id": 0, "x_field": "", "y_field": ""}, 200
            # print("Generated SQL:", sql)

        card_id = create_question(sql, db_id, collection_id, metadata['title'], metabase_url)
        embed_url = generate_embed_url(card_id, metabase_url)
        # print({"url": embed_url, "card_id": card_id, "x_field": metadata['x_axis'], "y_field": metadata['y_axis'], "visualization_options": metadata['visualization_options'], "SQL": sql})
        return {"url": embed_url, "card_id": card_id, "x_field": metadata['x_axis'], "y_field": metadata['y_axis'], "title": metadata["title"], "visualization_options": metadata['visualization_options'], "SQL": sql}, 200
    return ""

# Chat endpoints
@app.route("/api/chats", methods=["POST"])
def get_chats():
    """Get all chats for a user"""
    data = request.get_json()
    try:
        user_id = data.get("user_id")
        tenant_id = data.get("tenant_id")
        
        if not user_id:
            return abort(400, "user_id is required")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT chat_id, title, created_at, updated_at 
                    FROM chats 
                    WHERE user_id = %s AND tenant_id = %s 
                    ORDER BY updated_at DESC
                """, (user_id, tenant_id))
                
                chats = []
                for row in cur.fetchall():
                    chats.append({
                        "id": str(row[0]),
                        "title": row[1],
                        "created_at": row[2].isoformat(),
                        "updated_at": row[3].isoformat()
                    })
                
                return chats, 200
                
    except Exception as e:
        print(f"Error getting chats: {e}")
        return abort(500, "Internal server error")

@app.route("/api/chats/<chat_id>", methods=["POST"])
def get_chat(chat_id):
    """Get a specific chat and verify/recreate Metabase cards if needed"""
    data = request.get_json()
    try:
        user_id = data.get("user_id")
        
        if not user_id:
            return abort(400, "user_id is required")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get chat with metabase_url
                cur.execute("""
                    SELECT conversation, metabase_url, tenant_id
                    FROM chats 
                    WHERE chat_id = %s AND user_id = %s
                """, (chat_id, user_id))
                
                row = cur.fetchone()
                if not row:
                    return abort(404, "Chat not found")
                
                conversation = row[0]
                metabase_url = row[1]
                tenant_id = row[2]
                
                # Get all existing card IDs from Metabase
                existing_card_ids = get_all_card_ids(metabase_url)
                
                # Check each turn in the conversation
                updated_conversation = []
                for turn in conversation:
                    if 'embed' in turn and turn['embed'] and 'card_id' in turn['embed']:
                        card_id = turn['embed']['card_id']
                        
                        # If card doesn't exist in Metabase, recreate it
                        if card_id not in existing_card_ids:
                            # Extract necessary data from the turn
                            sql = turn['embed'].get('SQL', '')
                            title = turn['embed'].get('title', 'Untitled')
                            
                            if sql:
                                
                                db_id, collection_id = get_db_and_collection_id(tenant_id)
                                
                                # Create new question in Metabase
                                new_card_id = create_question(sql, db_id, collection_id, title, metabase_url)
                                
                                # Apply visualization settings if available
                                current_visualization = turn['embed'].get('current_visualization')
                                x_field = turn['embed'].get('x_field', [])
                                y_field = turn['embed'].get('y_field', [])
                                
                                if current_visualization and x_field and y_field:
                                    try:
                                        update_card_visualization(new_card_id, current_visualization, x_field, y_field, metabase_url)
                                    except Exception as e:
                                        print(f"Error updating visualization settings: {e}")
                                
                                new_embed_url = generate_embed_url(new_card_id, metabase_url)
                                
                                # Update the turn with new card_id and URL
                                turn['embed']['card_id'] = new_card_id
                                turn['embed']['url'] = new_embed_url
                    
                    updated_conversation.append(turn)
                
                # Update the conversation in the database if any cards were recreated
                if conversation != updated_conversation:
                    cur.execute("""
                        UPDATE chats 
                        SET conversation = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE chat_id = %s AND user_id = %s
                    """, (json.dumps(updated_conversation), chat_id, user_id))
                    conn.commit()
                
                return {"conversation": updated_conversation}, 200
                
    except Exception as e:
        print(f"Error getting chat: {e}")
        return abort(500, "Internal server error")

@app.route("/api/chats/save", methods=["POST"])
def save_chat():
    """Save or update a chat"""
    data = request.get_json()
    try:
        user_id = data.get("user_id")
        tenant_id = data.get("tenant_id")
        metabase_url = data.get("metabase_url")
        chat_id = data.get("chat_id")
        title = data.get("title")
        conversation = data.get("conversation")
        
        if not all([user_id, title, conversation]):
            return abort(400, "user_id, title, and conversation are required")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if chat_id:
                    # Update existing chat
                    cur.execute("""
                        UPDATE chats 
                        SET title = %s, conversation = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE chat_id = %s AND user_id = %s
                        RETURNING chat_id
                    """, (title, json.dumps(conversation), chat_id, user_id))
                    
                    row = cur.fetchone()
                    if not row:
                        return abort(404, "Chat not found")
                    
                    result_chat_id = str(row[0])
                else:
                    # Create new chat
                    cur.execute("""
                        INSERT INTO chats (user_id, tenant_id, metabase_url, title, conversation)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING chat_id
                    """, (user_id, tenant_id, metabase_url, title, json.dumps(conversation)))
                    
                    result_chat_id = str(cur.fetchone()[0])
                
                conn.commit()
                return {"chat_id": result_chat_id}, 200
                
    except Exception as e:
        print(f"Error saving chat: {e}")
        return abort(500, "Internal server error")

@app.route("/api/chats/<chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    """Delete a chat"""
    data = request.get_json()
    try:
        user_id = data.get("user_id")
        
        if not user_id:
            return abort(400, "user_id is required")
        
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM chats 
                    WHERE chat_id = %s AND user_id = %s
                """, (chat_id, user_id))
                
                if cur.rowcount == 0:
                    return abort(404, "Chat not found")
                
                conn.commit()
                return {"success": True}, 200
                
    except Exception as e:
        print(f"Error deleting chat: {e}")
        return abort(500, "Internal server error")

# Health check
@app.route("/")
def health_check():
    return "Backend is working!"

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "g":
        print("Beginning schema embedding process...")
        embed_schema()
        print("Finished embedding process.")
    else:
        print(f"Starting Flask app in {FLASK_ENV} mode with debug={app.config['DEBUG']}")
        app.run(host="0.0.0.0", port=5000, debug=app.config['DEBUG'], use_reloader=app.config['DEBUG'])