import { ChangeEvent, useEffect, useState } from "react";

type Novel = {
  id: string;
  title: string;
  author?: string;
  source_language: string;
  target_language: string;
};
type Chapter = { id: string; chapter_index: number; title: string; status: string };
type Translation = { id: string; unit_id: string; version: number; translated_text: string; model?: string };
type ChapterContent = { id: string; chapter_index: number; title: string; source_text: string; units: { unit_id: string; unit_index: number; source_text: string; translated_text?: string }[] };
type TranslationQAError = { code: string; unit_index: number; issues: { code: string; message: string }[] };
type NovelJob = { id: string; status: string; current_chapter_id?: string; total_chapters: number; processed_chapters: number; total_units: number; processed_units: number; failed_chapters: number };
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chapterPage, setChapterPage] = useState(0);
  const [chapterTotal, setChapterTotal] = useState(0);
  const [showChapters, setShowChapters] = useState(true);
  const [translations, setTranslations] = useState<Translation[]>([]);
  const [selected, setSelected] = useState<Novel | null>(null);
  const [message, setMessage] = useState("Loading library...");
  const [reviewId, setReviewId] = useState("");
  const [translatingId, setTranslatingId] = useState<string | null>(null);
  const [reader, setReader] = useState<ChapterContent | null>(null);
  const [readerMode, setReaderMode] = useState<"source" | "translation">("source");
  const [novelJob, setNovelJob] = useState<NovelJob | null>(null);

  const loadNovels = async () => {
    const response = await fetch(`${API}/api/v1/novels`);
    if (!response.ok) throw new Error("Unable to load library");
    setNovels((await response.json()).items);
    setMessage("Ready");
  };

  useEffect(() => {
    loadNovels().catch((error: Error) => setMessage(error.message));
  }, []);

  const chooseNovel = async (novel: Novel) => {
    setSelected(novel);
    setTranslations([]);
    setReader(null);
    setNovelJob(null);
    setShowChapters(true);
    await loadChapterPage(novel.id, 0);
  };

  const loadChapterPage = async (novelId: string, page: number) => {
    const response = await fetch(`${API}/api/v1/novels/${novelId}/chapters?offset=${page * 20}&limit=20`);
    if (!response.ok) {
      setMessage("Unable to load chapters");
      return;
    }
    const result = await response.json();
    setChapters(result.items);
    setChapterPage(page);
    setChapterTotal(result.total);
  };

  const openChapter = async (chapter: Chapter) => {
    setTranslations([]);
    const response = await fetch(`${API}/api/v1/chapters/${chapter.id}/content`);
    if (!response.ok) {
      setMessage("Unable to load chapter content");
      return;
    }
    setReader(await response.json());
    setReaderMode("source");
    const chapterTranslations = await fetch(`${API}/api/v1/chapters/${chapter.id}/translations`);
    if (chapterTranslations.ok) setTranslations(await chapterTranslations.json());
  };

  const importFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setMessage(`Importing ${file.name}...`);
    const response = await fetch(`${API}/imports?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      body: file,
    });
    setMessage(response.ok ? "Import complete" : "Import failed");
    if (response.ok) await loadNovels();
  };

  const translateChapter = async (chapter: Chapter, retryFailed = false) => {
    setTranslatingId(chapter.id);
    setMessage(`Translating ${chapter.title}...`);
    try {
      const endpoint = retryFailed ? "retry-failed" : "translate";
      const response = await fetch(`${API}/api/v1/chapters/${chapter.id}/${endpoint}`, { method: "POST" });
      if (!response.ok) {
        let errorMessage = "Translation failed";
        try {
          const payload = (await response.json()) as { detail?: TranslationQAError };
          if (payload.detail?.code === "translation_qa_failed") {
            const issues = payload.detail.issues.map((issue) => issue.code).join(", ");
            errorMessage = `Stopped at unit ${payload.detail.unit_index + 1}: ${issues}`;
          }
        } catch {
          // Keep the generic message when the server does not return JSON.
        }
        setMessage(errorMessage);
        setChapters((current) => current.map((item) => item.id === chapter.id ? { ...item, status: "failed" } : item));
        return;
      }
      const result = await response.json();
      const chapterTranslations = await fetch(`${API}/api/v1/chapters/${chapter.id}/translations`);
      setTranslations(chapterTranslations.ok ? await chapterTranslations.json() : []);
      if (reader?.id === chapter.id) await openChapter(chapter);
      setChapters((current) => current.map((item) => item.id === chapter.id ? { ...item, status: result.status } : item));
      setMessage(`Translated ${result.processed} units`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Translation request failed");
    } finally {
      setTranslatingId(null);
    }
  };

  const queueChapter = async (chapter: Chapter) => {
    setTranslatingId(chapter.id);
    setMessage(`Queueing ${chapter.title}...`);
    try {
      const response = await fetch(`${API}/api/v1/chapters/${chapter.id}/translation-jobs`, { method: "POST" });
      if (!response.ok) throw new Error("Unable to queue translation");
      const job = await response.json() as { id: string };
      for (let attempt = 0; attempt < 720; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const statusResponse = await fetch(`${API}/api/v1/jobs/${job.id}`);
        if (!statusResponse.ok) throw new Error("Unable to read translation job");
        const status = await statusResponse.json() as { status: string; processed: number; failed: number };
        setMessage(`Job ${status.status}: ${status.processed} processed, ${status.failed} failed`);
        if (["completed", "failed", "human_review"].includes(status.status)) {
          setChapters((current) => current.map((item) => item.id === chapter.id ? { ...item, status: status.status } : item));
          break;
        }
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Translation job failed");
    } finally {
      setTranslatingId(null);
    }
  };

  const queueNovel = async () => {
    if (!selected) return;
    setMessage(`Queueing all chapters in ${selected.title}...`);
    try {
      const response = await fetch(`${API}/api/v1/novels/${selected.id}/translation-jobs`, { method: "POST" });
      if (!response.ok) throw new Error("Unable to queue novel translation");
      const initial = await response.json() as NovelJob;
      setNovelJob(initial);
      for (let attempt = 0; attempt < 86400; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const statusResponse = await fetch(`${API}/api/v1/novel-translation-jobs/${initial.id}`);
        if (!statusResponse.ok) throw new Error("Unable to read novel translation progress");
        const status = await statusResponse.json() as NovelJob;
        setNovelJob(status);
        setMessage(`Novel job ${status.status}: ${status.processed_chapters}/${status.total_chapters} chapters, ${status.processed_units}/${status.total_units} units`);
        if (["completed", "failed", "human_review"].includes(status.status)) break;
      }
      await loadChapterPage(selected.id, chapterPage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Novel translation job failed");
    }
  };

  const deleteNovel = async (novel: Novel) => {
    if (!window.confirm(`Delete “${novel.title}” and all its chapters?`)) return;
    const response = await fetch(`${API}/api/v1/novels/${novel.id}`, { method: "DELETE" });
    if (!response.ok) {
      setMessage("Unable to delete novel");
      return;
    }
    if (selected?.id === novel.id) {
      setSelected(null);
      setChapters([]);
      setTranslations([]);
    }
    await loadNovels();
    setMessage(`Deleted ${novel.title}`);
  };

  return (
    <main>
      <header className="topbar">
        <div>
          <div className="brand-mark"><i /> TRANSLATION STUDIO</div>
          <h1>Novel Library</h1>
          <p className="subline">A quiet workspace for long-form translation and story memory.</p>
        </div>
        <label className="button">Import novel<input type="file" accept=".txt,.json,.epub" onChange={importFile} /></label>
      </header>
      <p className="status">{message}</p>
      <section className="review-bar">
        <div><span className="eyebrow">KNOWLEDGE REVIEW</span><strong>Human review actions</strong><small>Every change is written to the audit log.</small></div>
        <input placeholder="Candidate ID" value={reviewId} onChange={(event) => setReviewId(event.target.value)} />
        {["confirm", "reject", "merge", "split", "lock"].map((action) => (
          <button disabled={!reviewId} onClick={async () => {
            const response = await fetch(`${API}/api/v1/review/actions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, object_type: "entity", object_id: reviewId }) });
            setMessage(response.ok ? `Action ${action} recorded` : "Review action failed");
          }} key={action}>{action}</button>
        ))}
      </section>
      <section className="workspace">
        <aside><h2>Library <span className="library-count">{novels.length}</span></h2>{novels.length === 0 && <p className="muted">No novels imported.</p>}{novels.map((novel) => <div className="novel-row" key={novel.id}><button className={selected?.id === novel.id ? "novel active" : "novel"} onClick={() => chooseNovel(novel)}><strong>{novel.title}</strong><small>{novel.author ?? "Unknown author"}</small></button><button className="delete-novel" aria-label={`Delete ${novel.title}`} onClick={() => deleteNovel(novel)}>×</button></div>)}</aside>
        <article>
          <div className="panel-head"><div><span className="eyebrow">{selected ? "NOVEL" : "DASHBOARD"}</span><h2>{selected?.title ?? "Select a novel"}</h2></div>{selected && <span className="badge">{selected.target_language}</span>}</div>
           {selected && <div className="chapter-toolbar"><span>{chapterTotal.toLocaleString()} chapters</span><button onClick={() => setShowChapters((visible) => !visible)}>{showChapters ? "Close list" : "Open list"}</button><button disabled={translatingId !== null || novelJob?.status === "running" || novelJob?.status === "queued"} onClick={queueNovel}>Translate entire novel</button><a className="export-link" href={`${API}/api/v1/novels/${selected.id}/export?format=epub`} download>Export EPUB</a></div>}
           {novelJob && <div className="job-progress"><strong>Novel translation: {novelJob.status}</strong><span>{novelJob.processed_chapters}/{novelJob.total_chapters} chapters · {novelJob.processed_units}/{novelJob.total_units} units</span><progress max={Math.max(novelJob.total_units, 1)} value={novelJob.processed_units} /></div>}
           {selected && showChapters ? <><div className="chapters">{chapters.map((chapter) => <div className="chapter" key={chapter.id}><span>{String(chapter.chapter_index).padStart(3, "0")}</span><button className="chapter-title" onClick={() => openChapter(chapter)}>{chapter.title}</button><small>{chapter.status}</small><button disabled={translatingId !== null} onClick={() => translateChapter(chapter, chapter.status === "failed")}>{translatingId === chapter.id ? "Translating..." : chapter.status === "failed" ? "Retry failed" : "Translate"}</button><button disabled={translatingId !== null} onClick={() => queueChapter(chapter)}>Queue</button></div>)}</div><div className="pagination"><button disabled={chapterPage === 0} onClick={() => loadChapterPage(selected.id, chapterPage - 1)}>Previous</button><span>Page {chapterPage + 1} of {Math.max(1, Math.ceil(chapterTotal / 20))}</span><button disabled={(chapterPage + 1) * 20 >= chapterTotal} onClick={() => loadChapterPage(selected.id, chapterPage + 1)}>Next</button></div></> : selected ? <p className="muted">Chapter list closed. Open it to browse chapters.</p> : <p className="muted">Import a source file to start the translation workflow.</p>}
          {reader && <section className="reader"><div className="reader-head"><div><span className="eyebrow">READING VIEW</span><h3>{reader.title}</h3></div><div className="reader-tabs"><button className={readerMode === "source" ? "selected" : ""} onClick={() => setReaderMode("source")}>Original</button><button className={readerMode === "translation" ? "selected" : ""} onClick={() => setReaderMode("translation")}>Translation</button></div></div><div className="reader-body">{readerMode === "source" ? reader.source_text : reader.units.map((unit) => unit.translated_text ?? "[Not translated]").join("\n\n")}</div></section>}
          {translations.length > 0 && <section className="translation-results"><h3>Latest translations</h3>{translations.map((item) => <p key={item.id}>{item.translated_text}</p>)}</section>}
        </article>
      </section>
    </main>
  );
}
