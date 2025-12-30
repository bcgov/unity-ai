export type NormalizedTable = {
  columns: string[];
  rows: any[][];
  objects: Record<string, any>[];
};

function safeJsonParse<T = any>(value: any): T | null {
  if (value == null) return null;
  if (typeof value === "object") return value as T;
  if (typeof value !== "string") return null;

  try {
    return JSON.parse(value) as T;
  } catch (error) {
    console.log("error:", error)
    return null;
  }
}

export function normalizeCardData(cardDataRaw: any): NormalizedTable | null {
  const cardData = safeJsonParse<any>(cardDataRaw);
  console.log(cardData);
  if (!cardData) return null;

  // Case A: Metabase dataset-style: { data: { cols: [{name}], rows: [...] } }
  const colsA = cardData?.data?.cols;
  const rowsA = cardData?.data?.rows;
  if (Array.isArray(colsA) && Array.isArray(rowsA)) {
    const columns = colsA.map((c: any) => c?.display_name ?? c?.name ?? String(c));
    const rows = rowsA;
    const objects = rows.map((r: any[]) =>
      Object.fromEntries(columns.map((col, i) => [col, r?.[i]]))
    );
    return { columns, rows, objects };
  }

  // Case B: sometimes: { cols: [...], rows: [...] }
  const colsB = cardData?.cols;
  const rowsB = cardData?.rows;
  if (Array.isArray(colsB) && Array.isArray(rowsB)) {
    const columns = colsB.map((c: any) => c?.display_name ?? c?.name ?? String(c));
    const rows = rowsB;
    const objects = rows.map((r: any[]) =>
      Object.fromEntries(columns.map((col, i) => [col, r?.[i]]))
    );
    return { columns, rows, objects };
  }

  // Case C: already an array of objects: [{a:1,b:2}, ...]
  if (Array.isArray(cardData) && cardData.length && typeof cardData[0] === "object") {
    const columns = Array.from(
      new Set(cardData.flatMap((o: any) => Object.keys(o)))
    );
    const objects = cardData as Record<string, any>[];
    const rows = objects.map(obj => columns.map(c => obj?.[c]));
    return { columns, rows, objects };
  }

  // Case D: { results: [...] } where results is array of objects
  const resultsD = cardData?.results;
  if (Array.isArray(resultsD) && resultsD.length && typeof resultsD[0] === "object") {
    const columns = Array.from(new Set(resultsD.flatMap((o: any) => Object.keys(o))));
    const objects = resultsD as Record<string, any>[];
    const rows = objects.map(obj => columns.map(c => obj?.[c]));
    return { columns, rows, objects };
  }

  return null;
}
