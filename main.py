import dotenv
import os
import sys
import datetime as dt
from flask import Flask, request, render_template_string, abort, redirect
import time
import jwt
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
import json, textwrap, requests
from flask_cors import CORS
import shutil
import asyncio
import aiohttp
import os
import re
import hashlib, json
from collections import Counter

app = Flask(__name__)
CORS(app)

dotenv.load_dotenv()
headers = {"x-api-key": os.getenv("METABASE_KEY")}
MB_URL = "https://test-unity-reporting.apps.silver.devops.gov.bc.ca"

DB_ID = 3
COLLECTION_ID = 47
EMBED_WORKSHEETS = False
EMBED_SAMPLES = True
K = 7
PERSIST_DIR = "./embedded_schema"
SQL_BLOCK_RE = re.compile(r"```sql\s*(.+?)```", re.I | re.S)

os.makedirs(PERSIST_DIR, exist_ok=True) 

embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")
vector_store = Chroma(
    collection_name="embedded_schema",
    embedding_function=embedding_model,
    persist_directory="./embedded_schema"
)

def get_sql(sql):
    ds_req = {
        "database": DB_ID,
        "type": "native",
        "native": {"query": sql},
    }
    r = requests.post(
        f"{MB_URL}/api/dataset",
        headers=headers,
        json=ds_req,
    )
    r.raise_for_status()
    return r.json()["data"]

def extract_sql(text: str) -> str | None:
    m = SQL_BLOCK_RE.search(text)
    return m.group(1).strip() if m else None

def run_and_fingerprint(sql: str) -> tuple[str, tuple[str, ...], str]:
    """
    Returns (row_count, col_name_tuple, digest_of_first_5_rows)
    """
    data  = get_sql(sql)
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

    return docs

def embed_schema():
    
    vector_store.add_documents([Document(page_content=p.strip()) for p in get_table_schemas()])

    if EMBED_WORKSHEETS:
        vector_store.add_documents([Document(page_content=p.strip()) for p in get_parsed_worksheets()])

def sql_is_valid(sql: str, db_id: int) -> tuple[bool, str | None]:
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
    r = requests.post(f"{MB_URL}/api/dataset", headers=headers, json=payload)

    if r.status_code not in (200, 202):
        return False, f"HTTP {r.status_code}: {r.text}"

    body = r.json()
    if r.status_code == 202 and body.get("status") == "running":
        job_id = body["id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            jr = requests.get(f"{MB_URL}/api/async/{job_id}", headers=headers)
            if jr.status_code == 200:
                body = jr.json()
                break
            time.sleep(0.5)
    if "error" in body:
        return False, body["error"]

    return True, None

async def nl_to_sql(question, db_id):  

    entities = get_stream(
    f"""You are a SQL expert. Your task is to extract entities (such as table names, column names, and conditions) from a natural language question using few-shot learning. First, extract entities from the provided question, then the value retriever will use Locality Sensitive Hashing (LSH) and semantic similarity to find related database values.

Examples:
- Input: "top suppliers by spend last year"
  suppliers, orders, vendor names, amount, created_at.
- Input: "number of applications per status"
  applications, status.

Now, using this method, extract entities from the following natural language question:
"{question}"
    """,
        "gpt-4o"
    )

    retrieved = vector_store.similarity_search(entities, k=5)
    retrieved_tables = "\n".join(doc.page_content for doc in retrieved)

    with open("QDECOMP_examples.json", "r") as file:
        examples = json.load(file)
    examples = [f"### Schema:\n{'\n'.join(ex['Schema'])}\n### Question:\n{ex['Question']}\n### Reasoning:\n{ex['Reasoning']}\n### SQL:\n{ex['SQL']}" for ex in examples]
    prompt = f"{'\n\n'.join(examples)}\n\n### Schema:\n{retrieved_tables}\n### Question:\n{question}\n"

    print(prompt)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_chat_completion(prompt, "gpt-4o", session, i) for i in range(K)]
        completions = await asyncio.gather(*tasks)


    candidates = []
    for raw in completions:
        if not raw:
            continue
        sql = extract_sql(raw)
        print(sql)
        if not sql:
            continue

        ok, _ = sql_is_valid(sql, db_id)
        if not ok:
            continue

        try:
            fp = run_and_fingerprint(sql)
            candidates.append((fp, sql))
        except Exception as e:
            print("Exec error", e)
            continue

    # -------- majority vote on fingerprints --------
    fingerprints = [fp for fp, _ in candidates]
    winner_fp = majority(fingerprints)

    if winner_fp:
        for fp, sql in candidates:
            if fp == winner_fp:
                return sql                       # consensus winner
    # ---------- fallback ----------
    return candidates[0][1] if candidates else None

def create_question(sql: str, db_id: int, collection_id: int, name: str) -> int:
    r = requests.post(f"{MB_URL}/api/card", headers=headers, json={
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
    r2 = requests.put(f"{MB_URL}/api/card/{card_id}",
                      headers=headers,
                      json={"enable_embedding": True})
    if r2.status_code != 200:
        raise Exception(f"HTTP {r2.status_code}: {r2.text}")

    return card_id

def generate_embed_url(card_id: int) -> str:
    payload = {
        "resource": {"question": card_id},
        "params":   {}
    }
    token = jwt.encode(payload, os.getenv("MB_EMBED_SECRET"), algorithm="HS256")
    return f"{MB_URL}/embed/question/{token}?bordered=true&titled=false"

@app.route("/api/change_display", methods=["POST"])
def change_display():
    if request.method == "POST":
        data = request.get_json()
        mode = data.get("mode") if data else None
        card_id = data.get("card_id") if data else None
        x_field = data.get("x_field") if data else None
        y_field = data.get("y_field") if data else None
        if card_id == None or mode == None or x_field == None or y_field == None:
            return abort(400, "Missing inputs")

        r2 = requests.put(f"{MB_URL}/api/card/{card_id}",
            headers=headers,
            json={"display": mode,
                "visualization_settings": {
                    "graph.dimensions": x_field,
                    "graph.metrics": y_field
                }
            })
        if r2.status_code != 200:
            raise Exception(f"HTTP {r2.status_code}: {r2.text}")
        embed_url = generate_embed_url(card_id)
        return {"url": embed_url, "card_id": card_id, "x_field": x_field, "y_field": y_field}, 200
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
        question = data.get("question") if data else None
        if question is None:
            return abort(400, "Question is required")
        
        sql = await nl_to_sql(question, DB_ID)
        if sql == "fail":
            return {"url": "fail", "card_id": 0, "x_field": "", "y_field": ""}, 200
        print("Generated SQL:", sql)

        # TODO: make this a part of the query before it
        while True:
            try:
                fields = json.loads(get_stream("Please extract a title, and a list of x-axis and y-axis columns from the following SQL query, and output only json by itself with no markdown, example: '{\"title\": \"Number of Applicants and Amount Approved Per Month\", \"x_axis\": [\"month\"], \"y_axis\": [\"number_of_applicants\", \"amount_approved\"]}': " + sql, "o4-mini-2025-04-16").strip())
                title = fields["title"]
                x_field = fields["x_axis"]
                y_field = fields["y_axis"]
                break
            except:
                continue

        print("Extracted x-axis field:", x_field)
        print("Extracted y-axis field:", y_field)

        card_id = create_question(sql, DB_ID, COLLECTION_ID, title)
        embed_url = generate_embed_url(card_id)
        return {"url": embed_url, "card_id": card_id, "x_field": x_field, "y_field": y_field}, 200
    return ""

if len(sys.argv) > 1 and sys.argv[1] == "g":
    print("Beginning Embedding into memory...")
    embed_schema()
    print("Finished Embedding.")
else:
    app.run(host="0.0.0.0", port=5000, debug=True)