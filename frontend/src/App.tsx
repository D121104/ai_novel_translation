import { ChangeEvent, useEffect, useState } from "react";

type Novel = { id: string; title: string; author?: string; source_language: string; target_language: string };
type Chapter = { id: string; chapter_index: number; title: string; status: string };
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selected, setSelected] = useState<Novel | null>(null);
  const [message, setMessage] = useState("Loading library...");

  const loadNovels = async () => {
    const response = await fetch(`${API}/api/v1/novels`);
    if (!response.ok) throw new Error("Unable to load library");
    setNovels((await response.json()).items);
    setMessage("Ready");
  };
  useEffect(() => { loadNovels().catch((error: Error) => setMessage(error.message)); }, []);

  const chooseNovel = async (novel: Novel) => {
    setSelected(novel);
    const response = await fetch(`${API}/api/v1/novels/${novel.id}/chapters`);
    setChapters((await response.json()).items);
  };
  const importFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setMessage(`Importing ${file.name}...`);
    const response = await fetch(`${API}/imports?filename=${encodeURIComponent(file.name)}`, { method: "POST", body: file });
    setMessage(response.ok ? "Import complete" : "Import failed");
    if (response.ok) await loadNovels();
  };

  return <main>
    <header><div><span className="eyebrow">PERSONAL STUDIO</span><h1>Novel Library</h1></div><label className="button">Import novel<input type="file" accept=".txt,.json,.epub" onChange={importFile} /></label></header>
    <p className="status">{message}</p>
    <section className="workspace"><aside><h2>Library</h2>{novels.length === 0 && <p className="muted">No novels imported.</p>}{novels.map(novel => <button className={selected?.id === novel.id ? "novel active" : "novel"} onClick={() => chooseNovel(novel)} key={novel.id}><strong>{novel.title}</strong><small>{novel.author ?? "Unknown author"}</small></button>)}</aside>
      <article><div className="panel-head"><div><span className="eyebrow">{selected ? "NOVEL" : "DASHBOARD"}</span><h2>{selected?.title ?? "Select a novel"}</h2></div>{selected && <span className="badge">{selected.target_language}</span>}</div>{selected ? <div className="chapters">{chapters.map(chapter => <div className="chapter" key={chapter.id}><span>{String(chapter.chapter_index).padStart(3, "0")}</span><strong>{chapter.title}</strong><small>{chapter.status}</small></div>)}</div> : <p className="muted">Import a source file to start the translation workflow.</p>}</article>
    </section>
  </main>;
}
