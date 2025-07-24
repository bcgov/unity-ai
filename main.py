import dotenv
import os
import sys
import datetime as dt
from flask import Flask, request, abort
import time
import jwt
from langchain_chroma import Chroma
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

app = Flask(__name__)
CORS(app)

dotenv.load_dotenv()
headers = {"x-api-key": os.getenv("METABASE_KEY")}

EMBED_WORKSHEETS = False
EMBED_SAMPLES = True
K = 7
PERSIST_DIR = "./embedded_schema"
MODEL="gpt-4o-mini"

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "unity_ai")
DB_USER = os.getenv("DB_USER", "unity_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "unity_pass")
USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() == "true"

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

os.makedirs(PERSIST_DIR, exist_ok=True)

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

# Initialize vector store based on configuration
if USE_POSTGRES:
    vector_store = PGVector(
        embeddings=embedding_model,
        collection_name="embedded_schema",
        connection=DATABASE_URL,
        use_jsonb=True,
    )
else:
    vector_store = Chroma(
        collection_name="embedded_schema",
        embedding_function=embedding_model,
        persist_directory="./embedded_schema"
    )

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
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
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

def get_stream(input, model):
    api_url = "https://api.openai.com/v1/responses"
    api_key = os.getenv("OPENAI_API_KEY")
    headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    }

    data = {
        "model": model,
        "input": input,
        "stream": True,
    }

    output = ""

    with requests.post(api_url, headers=headers, json=data, stream=True) as response:
        for chunk in response.iter_lines():
            if chunk:
                try:
                    chunk_data = json.loads(chunk.decode("utf-8").lstrip("data: "))
                    if "delta" in chunk_data and chunk_data["delta"]:
                        delta = chunk_data["delta"]
                        # print(delta, end="")
                        output += delta
                except json.JSONDecodeError:
                    pass

    return output

def get_table_schemas():
    schema = requests.get(
        f"{MB_URL}/api/database/{DB_ID}/metadata",
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

def embed_schema():
    
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
    prompt = f"{f'{newline}{newline}'.join(examples)}{newline}{newline}### Schema:{newline}{retrieved_tables}{newline}### Question:{newline}The current date is {dt.datetime.now().strftime('%Y-%m-%d')}. {past_question_string}Please generate sql and metadata for the following question, with reasoning but no explanation: {question}{newline}### Reasoning:"

    # print(prompt)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_chat_completion(prompt, MODEL, session, i) for i in range(K)]
        completions = await asyncio.gather(*tasks)
    # completions = [get_stream(prompt, MODEL)]

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
                return sql, metadata
    # ---------- fallback ----------
    if candidates:
        return candidates[0][1]
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
        mode = data.get("mode") if data else None
        card_id = data.get("card_id") if data else None
        x_field = data.get("x_field") if data else None
        y_field = data.get("y_field") if data else None
        visualization_options = data.get("visualization_options") if data else None
        if card_id == None or mode == None or x_field == None or y_field == None:
            return abort(400, "Missing inputs")

        r2 = requests.put(f"{MB_URL}/api/card/{card_id}",
            headers=headers,
            json={"display": mode,
                "visualization_settings": {
                    "graph.dimensions": x_field,
                    "graph.metrics": y_field,
                    "map.region": "1c5d50ee-4389-4593-37c1-fa8d4687ff4c"
                }
            })
        if r2.status_code != 200:
            raise Exception(f"HTTP {r2.status_code}: {r2.text}")
        embed_url = generate_embed_url(card_id)
        return {"url": embed_url, "card_id": card_id, "x_field": x_field, "y_field": y_field, "visualization_options": visualization_options}, 200
    return ""

@app.route("/api/delete/<int:card_id>")
def delete_question(card_id: int):
    r = requests.delete(f"{MB_URL}/api/card/{card_id}", headers=headers)
    if r.status_code != 200 and r.status_code != 204:
        return {"success": False}
    return {"success": True}

@app.route("/api/ask", methods=["GET", "POST"])
async def ask():
    if request.method == "POST":

        data = request.get_json()
        if data:
            question = data.get("question") 
            conversation = data.get("conversation") 
            metabase_url = data.get("metabase_url")
            db_id = 3 if data.get("tenant_id") == "tenant123" else -1 # TODO: better way of mapping tenant id to MB DB id
            collection_id = data.get("collection_id") 

        else:
            return abort(400, "Data is required")
        
        if None in (metabase_url, db_id, collection_id):
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

        elif question == "Now make it only for 2024 Q3":
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
        return {"url": embed_url, "card_id": card_id, "x_field": metadata['x_axis'], "y_field": metadata['y_axis'], "visualization_options": metadata['visualization_options'], "SQL": sql}, 200
    return ""

# Health check
@app.route("/")
def health_check():
    return "Backend is working!"

if len(sys.argv) > 1 and sys.argv[1] == "g":
    print("Beginning Embedding into memory...")
    embed_schema()
    print("Finished Embedding.")
else:
    app.run(host="0.0.0.0", port=5000, debug=True)