import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

type Novel = {
  id: string;
  title: string;
  author?: string;
  source_language: string;
  target_language: string;
};
type Chapter = { id: string; chapter_index: number; title: string; status: string };
type Translation = {
  id: string;
  unit_id: string;
  version: number;
  translated_text: string;
  model?: string;
};
type ChapterContent = {
  id: string;
  chapter_index: number;
  title: string;
  source_text: string;
  units: {
    unit_id: string;
    unit_index: number;
    source_text: string;
    translated_text?: string;
  }[];
};
type TranslationQAError = {
  code: string;
  unit_index: number;
  issues: { code: string; message: string }[];
};
type NovelJob = {
  id: string;
  status: string;
  current_chapter_id?: string;
  total_chapters: number;
  processed_chapters: number;
  total_units: number;
  processed_units: number;
  failed_chapters: number;
};

type ReviewActionName = "confirm" | "reject" | "merge" | "split" | "lock";
const reviewActions: ReviewActionName[] = ["confirm", "reject", "merge", "split", "lock"];
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const formatStatus = (status: string) => status.replaceAll("_", " ");
const isTerminalJob = (status: string) =>
  ["completed", "failed", "human_review", "cancelled"].includes(status);
const isRetryableChapter = (status: string) => ["failed", "human_review"].includes(status);

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
  const [reviewOpen, setReviewOpen] = useState(false);
  const [libraryQuery, setLibraryQuery] = useState("");
  const [translatingId, setTranslatingId] = useState<string | null>(null);
  const [chapterJob, setChapterJob] = useState<{ id: string; chapterId: string } | null>(null);
  const [reader, setReader] = useState<ChapterContent | null>(null);
  const [readerMode, setReaderMode] = useState<"source" | "translation">("source");
  const [novelJob, setNovelJob] = useState<NovelJob | null>(null);
  const chapterCancelRequested = useRef(false);
  const novelCancelRequested = useRef(false);

  const loadNovels = async () => {
    const response = await fetch(`${API}/api/v1/novels`);
    if (!response.ok) throw new Error("Unable to load library");
    setNovels((await response.json()).items);
    setMessage("Library ready");
  };

  useEffect(() => {
    loadNovels().catch((error: Error) => setMessage(error.message));
  }, []);

  const filteredNovels = useMemo(() => {
    const query = libraryQuery.trim().toLowerCase();
    if (!query) return novels;
    return novels.filter((novel) =>
      `${novel.title} ${novel.author ?? ""}`.toLowerCase().includes(query),
    );
  }, [libraryQuery, novels]);

const translatedChapterCount = chapters.filter((chapter) =>
    ["translated", "completed", "human_review"].includes(chapter.status),
  ).length;

  const chooseNovel = async (novel: Novel) => {
    setSelected(novel);
    setTranslations([]);
    setReader(null);
    setNovelJob(null);
    setChapterJob(null);
    chapterCancelRequested.current = false;
    novelCancelRequested.current = false;
    setShowChapters(true);
    await loadChapterPage(novel.id, 0);
  };

  const loadChapterPage = async (novelId: string, page: number) => {
    const response = await fetch(
      `${API}/api/v1/novels/${novelId}/chapters?offset=${page * 20}&limit=20`,
    );
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
    const chapterTranslations = await fetch(
      `${API}/api/v1/chapters/${chapter.id}/translations`,
    );
    if (chapterTranslations.ok) setTranslations(await chapterTranslations.json());
  };

  const importFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setMessage(`Importing ${file.name}...`);
    const response = await fetch(
      `${API}/imports?filename=${encodeURIComponent(file.name)}`,
      { method: "POST", body: file },
    );
    setMessage(response.ok ? "Import complete" : "Import failed");
    if (response.ok) await loadNovels();
    event.target.value = "";
  };

  const translateChapter = async (chapter: Chapter, retryFailed = false) => {
    setTranslatingId(chapter.id);
    setMessage(`${retryFailed ? "Retrying" : "Translating"} ${chapter.title}...`);
    try {
      const endpoint = retryFailed ? "retry-failed" : "translate";
      const response = await fetch(
        `${API}/api/v1/chapters/${chapter.id}/${endpoint}`,
        { method: "POST" },
      );
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
        setChapters((current) =>
          current.map((item) =>
            item.id === chapter.id ? { ...item, status: "failed" } : item,
          ),
        );
        return;
      }
      const result = await response.json();
      const chapterTranslations = await fetch(
        `${API}/api/v1/chapters/${chapter.id}/translations`,
      );
      setTranslations(chapterTranslations.ok ? await chapterTranslations.json() : []);
      if (reader?.id === chapter.id) await openChapter(chapter);
      setChapters((current) =>
        current.map((item) =>
          item.id === chapter.id ? { ...item, status: result.status } : item,
        ),
      );
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
      const response = await fetch(
        `${API}/api/v1/chapters/${chapter.id}/translation-jobs`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("Unable to queue translation");
      const job = (await response.json()) as { id: string };
      chapterCancelRequested.current = false;
      setChapterJob({ id: job.id, chapterId: chapter.id });
      for (let attempt = 0; attempt < 720; attempt += 1) {
        if (chapterCancelRequested.current) break;
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const statusResponse = await fetch(`${API}/api/v1/jobs/${job.id}`);
        if (!statusResponse.ok) throw new Error("Unable to read translation job");
        const status = (await statusResponse.json()) as {
          status: string;
          processed: number;
          failed: number;
        };
        setMessage(
          `Job ${formatStatus(status.status)}: ${status.processed} processed, ${status.failed} failed`,
        );
        if (isTerminalJob(status.status)) {
          setChapters((current) =>
            current.map((item) =>
              item.id === chapter.id ? { ...item, status: status.status } : item,
            ),
          );
          break;
        }
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Translation job failed");
    } finally {
      setTranslatingId(null);
      setChapterJob(null);
    }
  };

  const cancelChapter = async () => {
    if (!chapterJob) return;
    chapterCancelRequested.current = true;
    const response = await fetch(`${API}/api/v1/jobs/${chapterJob.id}/cancel`, {
      method: "POST",
    });
    if (!response.ok) {
      chapterCancelRequested.current = false;
      setMessage("Unable to stop chapter translation");
      return;
    }
    setChapters((current) =>
      current.map((item) =>
        item.id === chapterJob.chapterId ? { ...item, status: "cancelled" } : item,
      ),
    );
    setMessage("Chapter translation stopped");
    setTranslatingId(null);
    setChapterJob(null);
  };

  const queueNovel = async () => {
    if (!selected) return;
    setMessage(`Queueing all chapters in ${selected.title}...`);
    try {
      const response = await fetch(
        `${API}/api/v1/novels/${selected.id}/translation-jobs`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("Unable to queue novel translation");
      const initial = (await response.json()) as NovelJob;
      setNovelJob(initial);
      novelCancelRequested.current = false;
      for (let attempt = 0; attempt < 86400; attempt += 1) {
        if (novelCancelRequested.current) break;
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const statusResponse = await fetch(
          `${API}/api/v1/novel-translation-jobs/${initial.id}`,
        );
        if (!statusResponse.ok) throw new Error("Unable to read novel translation progress");
        const status = (await statusResponse.json()) as NovelJob;
        setNovelJob(status);
        setMessage(
          `Novel job ${formatStatus(status.status)}: ${status.processed_chapters}/${status.total_chapters} chapters`,
        );
        if (isTerminalJob(status.status)) break;
      }
      await loadChapterPage(selected.id, chapterPage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Novel translation job failed");
    }
  };

  const cancelNovel = async () => {
    if (!novelJob || isTerminalJob(novelJob.status)) return;
    novelCancelRequested.current = true;
    const response = await fetch(
      `${API}/api/v1/novel-translation-jobs/${novelJob.id}/cancel`,
      { method: "POST" },
    );
    if (!response.ok) {
      novelCancelRequested.current = false;
      setMessage("Unable to stop novel translation");
      return;
    }
    const cancelled = (await response.json()) as NovelJob;
    setNovelJob(cancelled);
    setMessage("Novel translation stopped");
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

  const applyReviewAction = async (action: ReviewActionName) => {
    const response = await fetch(`${API}/api/v1/review/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, object_type: "entity", object_id: reviewId }),
    });
    setMessage(response.ok ? `${formatStatus(action)} action recorded` : "Review action failed");
  };

  const readerText = reader
    ? readerMode === "source"
      ? reader.source_text
      : reader.units.map((unit) => unit.translated_text ?? "[Not translated]").join("\n\n")
    : "";
  const readerWordCount = readerText.trim() ? readerText.trim().split(/\s+/).length : 0;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark"><i /> TRANSLATION STUDIO</div>
          <div className="topbar-copy">
            <span className="kicker">A personal reading room</span>
            <h1>Make every chapter<br /><em>feel at home.</em></h1>
            <p className="subline">Long-form translation with a memory for names, voices, and what the story has already revealed.</p>
          </div>
        </div>
        <div className="topbar-actions">
          <span className="local-note"><i /> Local workspace</span>
          <label className="button button-primary">
            <span className="button-plus">+</span> Import novel
            <input type="file" accept=".txt,.json,.epub" onChange={importFile} />
          </label>
        </div>
      </header>

      <div className="status-line" role="status"><span className="status-dot" />{message}</div>

      <section className="metric-strip" aria-label="Workspace overview">
        <div className="metric"><span>Library</span><strong>{novels.length.toString().padStart(2, "0")}</strong><small>novels on this device</small></div>
        <div className="metric"><span>Current shelf</span><strong>{selected ? chapterTotal.toLocaleString() : "—"}</strong><small>{selected ? "chapters in focus" : "choose a novel to begin"}</small></div>
        <div className="metric"><span>Page</span><strong>{selected ? `${chapterPage + 1}`.padStart(2, "0") : "—"}</strong><small>{selected ? `of ${Math.max(1, Math.ceil(chapterTotal / 20))}` : "ready when you are"}</small></div>
        <div className="metric metric-accent"><span>Translation memory</span><strong>{selected ? translatedChapterCount.toString().padStart(2, "0") : "∞"}</strong><small>{selected ? "translated this page" : "built as you work"}</small></div>
      </section>

      <section className="review-drawer">
        <button className="drawer-toggle" onClick={() => setReviewOpen((open) => !open)} aria-expanded={reviewOpen}>
          <span><span className="drawer-kicker">Knowledge review</span><strong>Keep the story canon in your hands.</strong></span>
          <span className="drawer-state">{reviewOpen ? "Close panel" : "Open review panel"} <b>{reviewOpen ? "−" : "+"}</b></span>
        </button>
        {reviewOpen && <div className="review-content">
          <p>Confirm, reject, merge, split, or lock a candidate. Every action is recorded in the audit log.</p>
          <input aria-label="Candidate ID" placeholder="Paste candidate ID" value={reviewId} onChange={(event) => setReviewId(event.target.value)} />
          <div className="review-actions">{reviewActions.map((action) => <button disabled={!reviewId} onClick={() => applyReviewAction(action)} key={action}>{formatStatus(action)}</button>)}</div>
        </div>}
      </section>

      <section className="workspace">
        <aside className="library-panel">
          <div className="library-heading">
            <div><span className="section-label">Your library</span><h2>Bookshelf</h2></div>
            <span className="library-count">{novels.length.toString().padStart(2, "0")}</span>
          </div>
          <label className="search-field"><span>⌕</span><input aria-label="Search library" placeholder="Find a novel" value={libraryQuery} onChange={(event) => setLibraryQuery(event.target.value)} /></label>
          <div className="shelf-list">
            {filteredNovels.length === 0 && <div className="empty-shelf"><span>—</span><p>{novels.length ? "No title matches that search." : "Your shelf is waiting."}</p><small>Import a TXT, JSON, or EPUB to start.</small></div>}
            {filteredNovels.map((novel) => <div className="novel-row" key={novel.id}>
              <button className={selected?.id === novel.id ? "novel active" : "novel"} onClick={() => chooseNovel(novel)}>
                <span className="novel-initial">{novel.title.slice(0, 1).toUpperCase()}</span>
                <span className="novel-copy"><strong>{novel.title}</strong><small>{novel.author ?? "Unknown author"}</small></span>
              </button>
              <button className="delete-novel" aria-label={`Delete ${novel.title}`} onClick={() => deleteNovel(novel)}>×</button>
            </div>)}
          </div>
          <div className="library-footer"><span className="live-mark" />Everything stays on your device</div>
        </aside>

        <article className="main-panel">
          {!selected ? <div className="welcome-state">
            <div className="welcome-copy"><span className="section-label">The studio</span><h2>A calm place to<br /><em>translate deeply.</em></h2><p>Start with one novel. The studio builds a living memory of its language, characters, and timeline while you work.</p><label className="button button-primary button-large">Import your first novel<input type="file" accept=".txt,.json,.epub" onChange={importFile} /></label></div>
            <div className="welcome-art" aria-hidden="true"><span className="orbit orbit-one" /><span className="orbit orbit-two" /><span className="book-shape"><i /><i /><i /></span><span className="art-caption">SOURCE<br /><b>→</b><br />STORY</span></div>
            <div className="workflow-note"><span>01</span><div><strong>Import a source</strong><small>EPUB, TXT, or JSON</small></div><span>02</span><div><strong>Translate in order</strong><small>Memory follows the story</small></div><span>03</span><div><strong>Read the result</strong><small>Export when ready</small></div></div>
          </div> : <>
            <div className="panel-head">
              <div><span className="section-label">Now reading</span><h2>{selected.title}</h2><p className="panel-meta">{selected.author ?? "Unknown author"} <span>·</span> {selected.source_language} → {selected.target_language}</p></div>
              <span className="language-badge">{selected.target_language}</span>
            </div>
            <div className="chapter-toolbar">
              <div className="toolbar-context"><span className="section-label">Chapter index</span><strong>{chapterTotal.toLocaleString()} chapters</strong></div>
              <div className="toolbar-actions"><button onClick={() => setShowChapters((visible) => !visible)}>{showChapters ? "Hide chapters" : "Show chapters"}</button><button className={novelJob && !isTerminalJob(novelJob.status) ? "button-danger" : "button-dark"} onClick={novelJob && !isTerminalJob(novelJob.status) ? cancelNovel : queueNovel}>{novelJob && !isTerminalJob(novelJob.status) ? "Stop all" : "Translate all"}</button><a className="export-link" href={`${API}/api/v1/novels/${selected.id}/export?format=epub`} download>Export EPUB</a></div>
            </div>
            {novelJob && <div className="job-progress"><div className="job-heading"><strong>Novel translation</strong><span className={`status-chip ${novelJob.status}`}>{formatStatus(novelJob.status)}</span></div><span>{novelJob.processed_chapters}/{novelJob.total_chapters} chapters <b>·</b> {novelJob.processed_units}/{novelJob.total_units} units</span><progress max={Math.max(novelJob.total_units, 1)} value={novelJob.processed_units} /></div>}
            {showChapters ? <>
              <div className="chapter-list-head"><span>Order</span><span>Chapter</span><span>Status</span><span>Actions</span></div>
              <div className="chapters">
                {chapters.length === 0 && <div className="empty-chapters"><span>—</span><strong>No chapters on this page.</strong><small>The source may still be processing.</small></div>}
                {chapters.map((chapter) => <div className="chapter" key={chapter.id}>
                  <span className="chapter-number">{String(chapter.chapter_index).padStart(3, "0")}</span>
                  <button className="chapter-title" onClick={() => openChapter(chapter)}><strong>{chapter.title}</strong><small>Open reading view</small></button>
                  <span className={`status-chip ${chapter.status}`}>{formatStatus(chapter.status)}</span>
                  <div className="chapter-actions">{chapterJob?.chapterId === chapter.id ? <button className="stop-button" onClick={cancelChapter}>Stop</button> : <><button disabled={translatingId !== null} onClick={() => translateChapter(chapter, isRetryableChapter(chapter.status))}>{translatingId === chapter.id ? "Working" : isRetryableChapter(chapter.status) ? "Retry" : "Translate"}</button><button className="queue-button" disabled={translatingId !== null} onClick={() => queueChapter(chapter)}>Queue</button></>}</div>
                </div>)}
              </div>
              <div className="pagination"><button disabled={chapterPage === 0} onClick={() => loadChapterPage(selected.id, chapterPage - 1)}>← Previous</button><span>Page {chapterPage + 1} <i /> {Math.max(1, Math.ceil(chapterTotal / 20))}</span><button disabled={(chapterPage + 1) * 20 >= chapterTotal} onClick={() => loadChapterPage(selected.id, chapterPage + 1)}>Next →</button></div>
            </> : <div className="closed-list"><span>Chapter list hidden</span><button onClick={() => setShowChapters(true)}>Show the list</button></div>}
            {reader && <section className="reader"><div className="reader-head"><div><span className="section-label">Reading view · chapter {reader.chapter_index}</span><h3>{reader.title}</h3><small>{readerWordCount.toLocaleString()} words in view</small></div><div className="reader-tabs"><button className={readerMode === "source" ? "selected" : ""} onClick={() => setReaderMode("source")}>Original</button><button className={readerMode === "translation" ? "selected" : ""} onClick={() => setReaderMode("translation")}>Translation</button></div></div><div className="reader-body">{readerText}</div></section>}
            {translations.length > 0 && <section className="translation-results"><div className="results-heading"><span className="section-label">Version history</span><h3>Latest translations</h3></div>{translations.map((item) => <p key={item.id}>{item.translated_text}</p>)}</section>}
          </>}
        </article>
      </section>
      <footer className="app-footer"><span>TRANSLATION STUDIO</span><span>Long-form work, one page at a time.</span><span>Local first · v0.1</span></footer>
    </main>
  );
}
