"use client";

import { useCallback, useRef, useState } from "react";
import {
  AnalysisResult,
  ApiError,
  CleaningPlan,
  GenerateResponse,
  downloadUrl,
  generateTemplate,
  uploadAndAnalyze,
} from "@/lib/api";

type Step = "upload" | "analyzing" | "review" | "variables" | "generate";

const STEPS: { id: Step; label: string }[] = [
  { id: "upload", label: "Upload" },
  { id: "analyzing", label: "Analisis" },
  { id: "review", label: "Review" },
  { id: "variables", label: "Variabel" },
  { id: "generate", label: "Generate" },
];

// Allowed user actions for uncertain/editable elements.
const ACTIONS: { value: string; label: string }[] = [
  { value: "keep", label: "Keep" },
  { value: "remove", label: "Remove" },
  { value: "keep_structure_clear_content", label: "Clear" },
];

export default function Home() {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [plan, setPlan] = useState<CleaningPlan | null>(null);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [variableValues, setVariableValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"clean_template" | "personalized">("clean_template");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File | null) => {
    setFile(f);
    setError(null);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const f = e.dataTransfer.files?.[0];
      if (f) handleFile(f);
    },
    [handleFile]
  );

  const startAnalyze = useCallback(async () => {
    if (!file) return;
    setError(null);
    setStep("analyzing");
    setResult(null);
    try {
      const result = await uploadAndAnalyze(file);
      setAnalysis(result);
      setPlan(result.cleaning_plan ?? null);
      setOverrides({});
      setVariableValues({});
      setStep("review");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menganalisis dokumen.");
      setStep("upload");
    }
  }, [file]);

  const applyOverride = useCallback(
    (target: string, action: string) => {
      setOverrides((prev) => ({ ...prev, [target]: action }));
    },
    []
  );

  const finalPlan = useCallback((): CleaningPlan => {
    if (!plan) return { operations: [], notes: [], warnings: [] };
    const byTarget = new Map(plan.operations.map((op) => [op.target, op]));
    for (const [target, action] of Object.entries(overrides)) {
      byTarget.set(target, { ...(byTarget.get(target) ?? { target }), target, action });
    }
    return { ...plan, operations: Array.from(byTarget.values()) };
  }, [plan, overrides]);

  const doGenerate = useCallback(async () => {
    if (!analysis || !plan) return;
    setError(null);
    // Map variable values keyed by variable id → placeholder ({{NAMA}} style).
    const payload: Record<string, string> = {};
    if (mode === "personalized") {
      for (const v of analysis.variables) {
        const val = variableValues[v.id];
        if (val && val.trim()) payload[v.placeholder] = val.trim();
      }
    }
    try {
      const resp = await generateTemplate(analysis.document_id, {
        mode,
        variables: payload,
        plan: finalPlan(),
      });
      setResult(resp);
      setStep("generate");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal membuat template.");
      // Auto-redirect to upload if session expired (404)
      if (err instanceof ApiError && err.status === 404) {
        setTimeout(() => {
          setStep("upload");
          setAnalysis(null);
          setPlan(null);
          setResult(null);
          setError("Session dokumen habis. Silakan upload ulang file .docx.");
        }, 500);
      }
    }
  }, [analysis, plan, mode, variableValues, finalPlan]);

  const stepIndex = STEPS.findIndex((s) => s.id === step);

  return (
    <div className="app">
      <div className="brand">
        <h1>DocuTemplate</h1>
        <span className="tagline">Ubah laporan lama menjadi template baru</span>
      </div>

      <div className="stepper">
        {STEPS.map((s, i) => (
          <span
            key={s.id}
            className={
              "step-chip" + (s.id === step ? " active" : i < stepIndex ? " done" : "")
            }
          >
            {i < stepIndex ? "✓" : `${i + 1}`} {s.label}
          </span>
        ))}
      </div>

      {error && <div className="error">{error}</div>}

      {step === "upload" && (
        <UploadStep
          file={file}
          onFile={handleFile}
          onDrop={onDrop}
          onBrowse={() => inputRef.current?.click()}
          inputRef={inputRef}
          onStart={startAnalyze}
        />
      )}

      {step === "analyzing" && (
        <div className="card">
          <div className="analyzing">
            <div className="spinner" />
            <div>
              <strong>Menganalisis dokumen…</strong>
              <div className="muted small">
                Membaca struktur, gaya, cover, BAB, subbagian, dan variabel secara nyata
                dari file Anda.
              </div>
            </div>
          </div>
        </div>
      )}

      {step === "review" && analysis && (
        <ReviewStep
          analysis={analysis}
          overrides={overrides}
          onOverride={applyOverride}
          onNext={() => setStep("variables")}
        />
      )}

      {step === "variables" && analysis && (
        <VariablesStep
          analysis={analysis}
          values={variableValues}
          onChange={setVariableValues}
          onBack={() => setStep("review")}
          onNext={() => setStep("generate")}
        />
      )}

      {step === "generate" && analysis && (
        <GenerateStep
          analysis={analysis}
          mode={mode}
          setMode={setMode}
          values={variableValues}
          result={result}
          onGenerate={doGenerate}
          onBack={() => setStep("variables")}
        />
      )}
    </div>
  );
}

/* ---------- Upload ---------- */

function UploadStep({
  file,
  onFile,
  onDrop,
  onBrowse,
  inputRef,
  onStart,
}: {
  file: File | null;
  onFile: (f: File | null) => void;
  onDrop: (e: React.DragEvent) => void;
  onBrowse: () => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
  onStart: () => void;
}) {
  const [dragging, setDragging] = useState(false);
  return (
    <div className="card hero">
      <h2>Ubah laporan lama menjadi template baru.</h2>
      <p>
        Upload laporan praktikum contoh dan DocuTemplate akan membantu membersihkan isi
        lama tanpa merusak struktur dokumennya.
      </p>
      <div
        className={"dropzone" + (dragging ? " dragging" : "")}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          setDragging(false);
          onDrop(e);
        }}
        onClick={onBrowse}
      >
        <div className="dz-title">{file ? file.name : "Drop DOCX di sini"}</div>
        <div className="dz-sub">
          {file ? `${(file.size / 1024).toFixed(0)} KB — klik untuk ganti` : "atau klik untuk memilih file"}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".docx"
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
      </div>
      <div style={{ marginTop: 16 }}>
        <button className="btn btn-primary" onClick={onStart} disabled={!file}>
          Upload DOCX
        </button>
      </div>
      <ul className="check">
        <li>Format .docx (Word) — satu file laporan contoh</li>
        <li>File Anda tidak disimpan permanen dan tidak pernah diubah</li>
      </ul>
    </div>
  );
}

/* ---------- Review (analysis summary + structure editor) ---------- */

function ReviewStep({
  analysis,
  overrides,
  onOverride,
  onNext,
}: {
  analysis: AnalysisResult;
  overrides: Record<string, string>;
  onOverride: (target: string, action: string) => void;
  onNext: () => void;
}) {
  const s = analysis.summary;
  const uncertain = analysis.uncertain_elements ?? [];
  return (
    <div>
      <div className="card">
        <h2>{analysis.source_name}</h2>
        <div className="stats">
          <Stat n={s.major_headings} label="BAB" />
          <Stat n={s.subheadings} label="Subbagian" />
          <Stat n={s.tables} label="Tabel" />
          <Stat n={s.images} label="Gambar" />
          <Stat n={s.variables} label="Variable" />
          <Stat n={s.paragraphs} label="Paragraf" />
        </div>
        <div className="muted small">
          Kertas {analysis.document_meta.page_layout.size_name ?? "custom"} ·{" "}
          {analysis.document_meta.page_layout.orientation} ·{" "}
          {analysis.document_meta.section_count} section
        </div>
      </div>

      <div className="card">
        <h2>Struktur</h2>
        <div className="tree">
          {analysis.structure.map((node) => (
            <Tree node={node} key={node.id} depth={0} />
          ))}
        </div>
      </div>

      {uncertain.length > 0 && (
        <div className="card">
          <h2>Perlu review</h2>
          <p className="muted small">
            Elemen di bawah ini terdeteksi dengan keyakinan sedang/rendah. Pilih
            tindakan — defaultnya disimpan.
          </p>
          {uncertain.map((id) => {
            const clf = analysis.classifications[id];
            const current = overrides[id] ?? "keep";
            return (
              <div className="row" key={id}>
                <div className="grow">
                  <div>{clf?.role ?? id}</div>
                  <div className="muted small">
                    confidence {(clf?.confidence ?? 0).toFixed(2)}
                  </div>
                </div>
                <div className="seg">
                  {ACTIONS.map((a) => (
                    <button
                      key={a.value}
                      className={current === a.value ? "on" : ""}
                      onClick={() => onOverride(id, a.value)}
                    >
                      {a.label}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <button className="btn btn-primary" onClick={onNext}>
        Lanjut ke Variabel →
      </button>
    </div>
  );
}

function Tree({ node, depth }: { node: AnalysisResult["structure"][number]; depth: number }) {
  return (
    <div>
      <div className={"node depth-" + depth}>
        {node.title ?? node.node_type}
        <span className={"badge " + (depth === 0 ? "badge-ok" : "badge-muted")}>
          {node.node_type}
        </span>
      </div>
      {node.children.map((c) => (
        <Tree node={c} depth={depth + 1} key={c.id} />
      ))}
    </div>
  );
}

function Stat({ n, label }: { n: number; label: string }) {
  return (
    <div className="stat">
      <div className="num">{n}</div>
      <div className="lbl">{label}</div>
    </div>
  );
}

/* ---------- Variables ---------- */

function VariablesStep({
  analysis,
  values,
  onChange,
  onBack,
  onNext,
}: {
  analysis: AnalysisResult;
  values: Record<string, string>;
  onChange: (v: Record<string, string>) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const vars = analysis.variables;
  return (
    <div className="card">
      <h2>Variabel terdeteksi</h2>
      <p className="muted small">
        Nilai lama akan diganti placeholder. Di mode personal, isi nilai baru untuk
        langsung masuk ke template.
      </p>
      {vars.length === 0 && <p className="muted">Tidak ada variabel identitas terdeteksi.</p>}
      {vars.map((v) => {
        const enabled = v.id in values;
        return (
          <div className="row" key={v.id}>
            <div className="grow">
              <div>
                <strong>{v.label}</strong>{" "}
                <span className="badge badge-muted">{v.placeholder}</span>
              </div>
              <div className="muted small">
                Nilai lama: {v.original_value || "—"} · {v.location}
              </div>
            </div>
            <div className="field" style={{ margin: 0, minWidth: 180 }}>
              <input
                placeholder={v.placeholder}
                value={values[v.id] ?? ""}
                disabled={!enabled}
                onChange={(e) =>
                  onChange({ ...values, [v.id]: e.target.value })
                }
              />
            </div>
            <button
              className={"btn " + (enabled ? "btn-primary" : "btn-ghost")}
              onClick={() => {
                const next = { ...values };
                if (enabled) delete next[v.id];
                else next[v.id] = "";
                onChange(next);
              }}
            >
              {enabled ? "Isi" : "Lewati"}
            </button>
          </div>
        );
      })}
      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button className="btn" onClick={onBack}>
          ← Review
        </button>
        <button className="btn btn-primary" onClick={onNext}>
          Lanjut ke Generate →
        </button>
      </div>
    </div>
  );
}

/* ---------- Generate ---------- */

function GenerateStep({
  analysis,
  mode,
  setMode,
  values,
  result,
  onGenerate,
  onBack,
}: {
  analysis: AnalysisResult;
  mode: "clean_template" | "personalized";
  setMode: (m: "clean_template" | "personalized") => void;
  values: Record<string, string>;
  result: GenerateResponse | null;
  onGenerate: () => void;
  onBack: () => void;
}) {
  return (
    <div>
      <div className="card">
        <h2>Mode output</h2>
        <div className="seg" style={{ marginBottom: 16 }}>
          <button className={mode === "clean_template" ? "on" : ""} onClick={() => setMode("clean_template")}>
            Template bersih (placeholder)
          </button>
          <button className={mode === "personalized" ? "on" : ""} onClick={() => setMode("personalized")}>
            Laporan baru (terisi)
          </button>
        </div>
        <p className="muted small">
          {mode === "clean_template"
            ? "Semua variabel menjadi placeholder seperti {{NAMA}} — cocok dibagikan."
            : "Nilai yang Anda isi di langkah Variabel akan langsung masuk ke template."}
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={onBack}>
            ← Variabel
          </button>
          <button className="btn btn-primary" onClick={onGenerate}>
            Generate DOCX
          </button>
        </div>
      </div>

      {result && (
        <div className="card">
          <div className="result-ok">✓ Template berhasil dibuat</div>
          <ul className="check">
            <li>{result.summary.replaced_variables} variable diganti</li>
            <li>{result.summary.cleared_paragraphs} paragraf lama dibersihkan</li>
            <li>{result.summary.removed_images} gambar lama dihapus</li>
            <li>{result.summary.cleared_tables} tabel dibersihkan</li>
            <li>Struktur dan format dipertahankan</li>
          </ul>
          <div style={{ marginTop: 12 }}>
            <a className="btn btn-primary" href={downloadUrl(analysis.document_id)}>
              ⬇ Download DOCX
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
