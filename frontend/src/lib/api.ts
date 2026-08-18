// API client for the PraktiKit backend (FastAPI).
// The backend URL is configurable via NEXT_PUBLIC_API_URL (defaults to localhost:8000).

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export interface AnalysisSummary {
  paragraphs: number;
  tables: number;
  images: number;
  sections: number;
  major_headings: number;
  subheadings: number;
  variables: number;
}

export interface HeadingInfo {
  block_id: string;
  level: number;
  title: string;
  number?: string | null;
  confidence: number;
  reasons: string[];
}

export interface VariableField {
  id: string;
  label: string;
  original_value: string;
  placeholder: string;
  standard: boolean;
  location: string;
}

export interface StructureNode {
  id: string;
  node_type: string;
  title?: string | null;
  number?: string | null;
  level: number;
  children: StructureNode[];
}

export interface DocumentMeta {
  page_layout: { size_name?: string | null; orientation: string };
  margins: { top?: number | null; bottom?: number | null; left?: number | null; right?: number | null };
  section_count: number;
}

export interface Classification {
  block_id: string;
  role: string;
  confidence: number;
  automation: string;
  reasons: string[];
}

export interface CleaningOperation {
  target: string;
  action: string;
  placeholder?: string | null;
  reason?: string | null;
}

export interface CleaningPlan {
  operations: CleaningOperation[];
  notes: string[];
  warnings: string[];
}

export interface AnalysisResult {
  document_id: string;
  source_name: string;
  document_meta: DocumentMeta;
  summary: AnalysisSummary;
  structure: StructureNode[];
  headings: HeadingInfo[];
  classifications: Record<string, Classification>;
  variables: VariableField[];
  cleaning_plan?: CleaningPlan | null;
  warnings: string[];
  uncertain_elements: string[];
}

export interface GenerateResponse {
  document_id: string;
  filename: string;
  download_url: string;
  summary: {
    replaced_variables: number;
    cleared_paragraphs: number;
    removed_images: number;
    cleared_tables: number;
  };
}

export async function uploadAndAnalyze(file: File): Promise<AnalysisResult> {
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch(`${API_URL}/api/documents/analyze`, { method: "POST", body: form });
  if (!resp.ok) throw new ApiError(await readError(resp), resp.status);
  const data = await resp.json();
  // The session id is the authoritative document id for generate/download.
  // Prefer the response root value; fall back to the nested analysis id.
  const documentId = data.document_id ?? data.analysis?.document_id;
  return { ...data.analysis, document_id: documentId };
}

export async function generateTemplate(
  documentId: string,
  opts: {
    mode: "clean_template" | "personalized";
    variables?: Record<string, string>;
    plan?: CleaningPlan | null;
  }
): Promise<GenerateResponse> {
  const resp = await fetch(`${API_URL}/api/documents/${documentId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: opts.mode,
      variables: opts.variables ?? {},
      cleaning_plan: opts.plan ?? undefined,
    }),
  });
  if (!resp.ok) throw new ApiError(await readError(resp), resp.status);
  return resp.json();
}

export function downloadUrl(documentId: string): string {
  return `${API_URL}/api/documents/${documentId}/download`;
}

async function readError(resp: Response): Promise<string> {
  try {
    const data = await resp.json();
    return data.detail ?? data.detail ?? `HTTP ${resp.status}`;
  } catch {
    return `HTTP ${resp.status}`;
  }
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
