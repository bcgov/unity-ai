"""
SQL generation module for natural language to SQL conversion.
Uses LLM with majority voting for robust SQL generation.
"""
import re
import json
import hashlib
import asyncio
import aiohttp
import tiktoken
import datetime as dt
from typing import Dict, Any, List, Optional, Tuple
from collections import Counter
from config import config
from embeddings import embedding_manager
from metabase import metabase_client


class SQLGenerator:
    """Generates SQL from natural language queries"""
    
    def __init__(self):
        self.config = config.ai
        self.metabase = metabase_client
        self.embeddings = embedding_manager
        self.tokenizer = tiktoken.encoding_for_model("gpt-4o-mini")
        
        # Regex patterns for extraction
        self.sql_pattern = re.compile(r"```sql\s*(.+?)```", re.I | re.S)
        self.metadata_pattern = re.compile(
            r"""\#\#\#\s*Metadata:\s*
                (?:```json\s*)?
                (\{.*?})
                (?:\s*```)?
            """,
            re.IGNORECASE | re.DOTALL | re.VERBOSE
        )
    
    def extract_sql(self, text: str) -> Optional[str]:
        """Extract SQL from LLM response"""
        # Try code fence first
        match = self.sql_pattern.search(text)
        if match:
            return match.group(1).strip()
        
        # Fallback: look for '### SQL:' header
        sql_header = re.search(r"### SQL:\s*([\s\S]+?)(?:\n###|\Z)", text)
        if sql_header:
            return sql_header.group(1).strip()
        
        return None
    
    def extract_metadata(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract metadata from LLM response"""
        match = self.metadata_pattern.search(text)
        if not match:
            return None
        
        raw = match.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    
    def fingerprint_results(self, sql: str, db_id: int) -> Tuple[str, Tuple[str, ...], str]:
        """
        Create a fingerprint of SQL results for comparison.
        
        Returns:
            Tuple of (row_count, column_names, hash_of_first_5_rows)
        """
        data = self.metabase.execute_sql(sql, db_id)
        rows = data["rows"]
        cols = tuple(
            c["name"] if isinstance(c, dict) else c
            for c in data["cols"]
        )
        head = rows[:5]
        digest = hashlib.md5(json.dumps(head, default=str).encode()).hexdigest()
        return str(len(rows)), cols, digest
    
    def find_majority(self, items: List) -> Optional[Any]:
        """Find the most common item if it appears more than once"""
        if not items:
            return None
        counts = Counter(items)
        winner, freq = counts.most_common(1)[0]
        return winner if freq > 1 else None
    
    async def fetch_completion(self, prompt: str, session: aiohttp.ClientSession, 
                              index: int) -> Optional[str]:
        """Fetch a single completion from the LLM"""
        print(f"[{index}] Tokens in prompt: {len(self.tokenizer.encode(prompt))}")
        
        headers = {
            "Authorization": f"Bearer {self.config.completion_key}",
            "Content-Type": "application/json"
        }
        
        json_data = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.temperature
        }
        
        async with session.post(
            self.config.completion_endpoint,
            headers=headers,
            json=json_data
        ) as response:
            if response.status != 200:
                print(f"[{index}] Error: {response.status}")
                print(await response.text())
                return None
            
            data = await response.json()
            print(f"[{index}] Tokens used: {data['usage']['total_tokens']}")
            return data["choices"][0]["message"]["content"]
    
    def load_examples(self) -> List[str]:
        """Load example queries for few-shot prompting"""
        try:
            with open("QDECOMP_examples.json", "r") as file:
                examples = json.load(file)
            
            formatted = []
            for ex in examples:
                newline = '\n'
                metadata_dict = {
                    'title': ex['title'],
                    'x_axis': ex['x_axis'], 
                    'y_axis': ex['y_axis'],
                    'visualization_options': ex['visualization_options']
                }
                formatted.append(
                    f"### Schema:{newline}{newline.join(ex['Schema'])}{newline}"
                    f"### Question:{newline}{ex['Question']}{newline}"
                    f"### Reasoning:{newline}{ex['Reasoning']}{newline}"
                    f"### SQL:{newline}{ex['SQL']}{newline}"
                    f"### Metadata:{newline}{json.dumps(metadata_dict)}"
                )
            return formatted
        except FileNotFoundError:
            print("Warning: QDECOMP_examples.json not found, using empty examples")
            return []
    
    def build_prompt(self, question: str, schemas: str, 
                    past_questions: List[Dict]) -> str:
        """Build the prompt for SQL generation"""
        examples = self.load_examples()
        newline = '\n'
        
        # Add past question context if available
        past_context = ""
        if past_questions and len(past_questions) > 1:
            last_q = past_questions[-2]
            past_context = (
                f'Note that the previous question in this conversation was: '
                f'"{last_q["question"]}" and the generated SQL was: "{last_q["SQL"]}". '
            )
        
        prompt = (
            f"{f'{newline}{newline}'.join(examples)}{newline}{newline}"
            f"### Schema:{newline}{schemas}{newline}"
            f"### Question:{newline}"
            f"The current date is {dt.datetime.now().strftime('%Y-%m-%d')}. "
            f"{past_context}"
            f"Please generate sql and metadata for the following question, "
            f"with reasoning but no explanation. "
            f"Please enable map option only for questions involving regional districts: "
            f"{question}{newline}"
            f"### Reasoning:"
        )
        
        return prompt
    
    async def generate_sql(self, question: str, past_questions: List[Dict],
                          db_id: int) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Generate SQL from natural language question using majority voting.
        
        Args:
            question: Natural language question
            past_questions: List of past questions and SQL
            db_id: Database ID
            
        Returns:
            Tuple of (sql, metadata) or (None, None) if generation fails
        """
        # Check for hardcoded examples first (can be removed in production)
        hardcoded = self._check_hardcoded_examples(question)
        if hardcoded:
            return hardcoded
        
        # Get relevant schemas
        schemas = self.embeddings.get_formatted_schemas(question, db_id)
        
        # Build prompt
        prompt = self.build_prompt(question, schemas, past_questions)
        print("Prompt:", prompt[:500] + "...")
        
        # Generate multiple completions in parallel
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.fetch_completion(prompt, session, i)
                for i in range(self.config.k_samples)
            ]
            completions = await asyncio.gather(*tasks)
        
        # Process completions and extract valid candidates
        candidates = []
        for raw in completions:
            if not raw:
                continue
            
            sql = self.extract_sql(raw)
            if not sql:
                print("No SQL found in completion")
                continue
            
            metadata = self.extract_metadata(raw)
            if not metadata:
                print("No metadata found in completion")
                continue
            
            # Validate SQL
            is_valid, error = self.metabase.validate_sql(sql, db_id)
            if not is_valid:
                print(f"SQL validation failed: {error}")
                continue
            
            # Generate fingerprint
            try:
                fingerprint = self.fingerprint_results(sql, db_id)
                candidates.append((fingerprint, sql, metadata))
            except Exception as e:
                print(f"Error generating fingerprint: {e}")
                continue
        
        # Majority voting on fingerprints
        if candidates:
            fingerprints = [fp for fp, _, _ in candidates]
            winner_fp = self.find_majority(fingerprints)
            
            if winner_fp:
                # Return the first candidate with winning fingerprint
                for fp, sql, metadata in candidates:
                    if fp == winner_fp:
                        print(f"Majority vote winner: {sql[:100]}...")
                        return sql, metadata
            
            # Fallback to first valid candidate
            print("No majority, using first candidate")
            return candidates[0][1], candidates[0][2]
        
        print("No valid candidates generated")
        return None, None
    
    def _check_hardcoded_examples(self, question: str) -> Optional[Tuple[str, Dict]]:
        """Check for hardcoded example queries (for demo/testing)"""
        examples = {
            "How many applications were approved in each subsector?": (
                '''SELECT COALESCE(applicants."SubSector", 'Unspecified') AS SubSector, 
COUNT(*) AS TotalApplications
FROM "public"."Applications" AS applications
JOIN "public"."Applicants" AS applicants ON applications."ApplicantId" = applicants."Id"
WHERE applicants."SubSector" IS NOT NULL 
AND applicants."SubSector" != '' 
AND LOWER(applicants."SubSector") != 'other'
GROUP BY applicants."SubSector"
ORDER BY TotalApplications DESC 
LIMIT 15;''',
                {
                    "title": "Approved Applications Per Subsector",
                    "x_axis": ['SubSector'],
                    "y_axis": ['TotalApplications'],
                    "visualization_options": ["bar", "pie"]
                }
            ),
            "Total applications and distributed funding per month in 2024": (
                '''SELECT 
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
    month;''',
                {
                    "title": "Total Applicants and Approved Funding Per Month in 2024",
                    "x_axis": ["month"],
                    "y_axis": ["total_applicants", "total_approved_funding"],
                    "visualization_options": ["bar", "line"]
                }
            ),
            "Distribution of funding by regional district": (
                '''SELECT "public"."Applications"."RegionalDistrict" AS "RegionalDistrict",
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
"public"."Applications"."RegionalDistrict" ASC''',
                {
                    "title": "Approved Amount per Regional District",
                    "x_axis": ["RegionalDistrict"],
                    "y_axis": ["sum"],
                    "visualization_options": ["bar", "pie", "map"]
                }
            )
        }
        
        if question in examples:
            return examples[question]
        return None


# Global SQL generator instance
sql_generator = SQLGenerator()