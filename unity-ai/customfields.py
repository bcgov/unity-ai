import main
import os
import json
import dotenv
import textwrap

dotenv.load_dotenv()

def get_worksheets():
    sql = f'SELECT "Worksheets"."Name", "Worksheets"."Id" FROM "Flex"."Worksheets"'
    data = main.get_sql(sql, 3, os.getenv("MB_URL"))
    return [{"name": r[0], "id": r[1]} for r in data["rows"]]

def get_worksheet_instances(worksheetId):
    sql = f'SELECT "WorksheetInstances"."CurrentValue", "WorksheetInstances"."WorksheetCorrelationId" FROM "Flex"."WorksheetInstances" WHERE "WorksheetInstances"."WorksheetId" = \'{worksheetId}\''
    data = main.get_sql(sql, 3, os.getenv("MB_URL"))
    return data

def get_custom_labels():
    all_data = {}
    batch_size = 500
    offset = 0

    while True:
        sql = f'''
        SELECT "CustomFields"."Label", "CustomFields"."Key"
        FROM "Flex"."CustomFields"
        ORDER BY "CustomFields"."Key"
        LIMIT {batch_size} OFFSET {offset}
        '''
        rows = main.get_sql(sql, 3, os.getenv("MB_URL"))["rows"]

        if not rows:
            break

        all_data.update({r[1]: r[0] for r in rows})
        offset += batch_size

    return all_data

def get_parsed_worksheets():
    parsed = []
    worksheets = get_worksheets()
    custom_labels = get_custom_labels()
    for w in worksheets:
        instance = get_worksheet_instances(w["id"])
        if len(instance["rows"]) > 0 and "values" in json.loads(instance["rows"][0][0]):
            rows = instance["rows"]
            keys = [j["key"] for j in json.loads(rows[0][0])["values"]]

            samples = []
            for row in rows[:3]:
                keys = [j["key"] for j in json.loads(row[0])["values"]]
                values = [j["value"] for j in json.loads(row[0])["values"]]
                samples.append({custom_labels[keys[i]]: values[i][:300] for i in range(len(keys))})

            parsed_string = f'''### {w["name"]}
**Columns**
{"\n".join(["- **" + custom_labels[k] + "** type/Text" for k in keys])}


**Relations**
_(none)_

{"**Samples** (up to 3 rows)\n" + textwrap.indent(
    json.dumps(samples, indent=2, default=str),
    "    ")}
        '''
            parsed.append(parsed_string)
    return parsed


print(get_worksheets())

'''
**Extraction pattern (PostgreSQL)**
```sql
SELECT  wi."Id" AS WorksheetInstanceId,
        {"\n".join(["MAX(CASE WHEN elem ->> 'key' = '" + k + "' THEN elem ->> 'value' END) AS \"" + k + "\"," for k in keys])}
FROM    Flex."WorksheetInstances"  wi
CROSS   JOIN LATERAL jsonb_array_elements(wi."CurrentValue" -> 'values') elem
GROUP BY wi."Id"
'''