#!/usr/bin/env python3
"""Auditoria E2E: falhas, tempos e aderência aos pilares do VideoViral."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings


def _rel_path(p: Path | str) -> str:
    path = Path(p).resolve()
    return str(path.relative_to(ROOT.resolve())).replace("\\", "/")


@dataclass
class CheckResult:
    name: str
    pillar: str
    ok: bool
    seconds: float = 0.0
    detail: str = ""


@dataclass
class AuditReport:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, pillar: str, ok: bool, seconds: float = 0, detail: str = "") -> None:
        self.checks.append(CheckResult(name, pillar, ok, seconds, detail))

    def print_report(self) -> int:
        fails = [c for c in self.checks if not c.ok]
        print("\n" + "=" * 60)
        print("RELATORIO DE AUDITORIA — VideoViral")
        print("=" * 60)
        for c in self.checks:
            icon = "OK" if c.ok else "FALHA"
            t = f" ({c.seconds:.1f}s)" if c.seconds else ""
            print(f"[{icon}] {c.name}{t}")
            if c.detail:
                print(f"      {c.detail}")
        print("-" * 60)
        print(f"Total: {len(self.checks)} | OK: {len(self.checks)-len(fails)} | Falhas: {len(fails)}")
        by_pillar: dict[str, list[CheckResult]] = {}
        for c in self.checks:
            by_pillar.setdefault(c.pillar, []).append(c)
        print("\nPor pilar (objetivo do app):")
        for pillar, items in by_pillar.items():
            ok_n = sum(1 for i in items if i.ok)
            print(f"  {pillar}: {ok_n}/{len(items)}")
        return 1 if fails else 0


def _ffprobe_video(path: Path) -> dict | None:
    if not path.exists():
        return None
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,r_frame_rate",
        "-of", "json", str(path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        s = json.loads(r.stdout).get("streams", [{}])[0]
        return {
            "width": int(s.get("width", 0)),
            "height": int(s.get("height", 0)),
            "duration": float(s.get("duration", 0)),
        }
    except Exception:
        return None


def run_audit(skip_download: bool = False) -> int:
    report = AuditReport()

    # Config
    gemini_ok = bool(settings.gemini_api_key)
    openai_ok = bool(settings.openai_api_key)
    openai_valid = openai_ok and settings.openai_api_key.startswith("sk")
    youtube_ok = bool(settings.youtube_api_key)

    report.add("Config GEMINI", "Infra", gemini_ok, detail="chave presente" if gemini_ok else "vazia")
    report.add(
        "Config OPENAI (formato sk-)",
        "Pilar 2",
        openai_valid,
        detail="OK" if openai_valid else "chave AIza no OPENAI — Whisper falha",
    )
    report.add("Config YOUTUBE API", "Pilar 1", youtube_ok, detail="opcional; yt-dlp funciona sem")

    # Download
    if not skip_download:
        t0 = time.perf_counter()
        try:
            from src.downloader import download_video

            path = download_video("https://www.youtube.com/shorts/jNQXAC9IVRw")
            dt = time.perf_counter() - t0
            size_mb = Path(path).stat().st_size / 1024 / 1024
            report.add("Download yt-dlp", "Pilar 1", True, dt, f"{path.name} ({size_mb:.1f} MB)")
            test_video = Path(path)
        except Exception as e:
            report.add("Download yt-dlp", "Pilar 1", False, time.perf_counter() - t0, str(e)[:200])
            test_video = None
    else:
        raw = list((settings.storage_path / "raw").glob("*.mp4"))
        test_video = raw[0] if raw else None
        report.add(
            "Download yt-dlp",
            "Pilar 1",
            test_video is not None,
            detail=f"reuso {test_video.name}" if test_video else "sem mp4 em raw/",
        )

    # Gemini
    t0 = time.perf_counter()
    try:
        from src.llm import call_llm

        call_llm('Responda JSON: {"ok":true}')
        report.add("Gemini / LLM", "Pilar 2", True, time.perf_counter() - t0)
    except Exception as e:
        report.add("Gemini / LLM", "Pilar 2", False, time.perf_counter() - t0, str(e)[:200])

    # Whisper
    if test_video and openai_valid:
        t0 = time.perf_counter()
        try:
            from src.transcription import transcribe_video

            segs, _ = transcribe_video(test_video)
            report.add(
                "Whisper real",
                "Pilar 2",
                len(segs) > 0,
                time.perf_counter() - t0,
                f"{len(segs)} segmentos",
            )
        except Exception as e:
            report.add("Whisper real", "Pilar 2", False, time.perf_counter() - t0, str(e)[:200])
    else:
        report.add(
            "Whisper real",
            "Pilar 2",
            False,
            detail="pulado — sem video ou OPENAI invalida",
        )

    # Pipeline clip (mock whisper se needed)
    if test_video:
        t0 = time.perf_counter()
        try:
            from src.pipeline.example_clip_flow import run_pipeline

            mock = not openai_valid
            res = run_pipeline(test_video, niche="curiosidades", mock_transcribe=mock)
            clip = Path(res["clip"])
            dt = time.perf_counter() - t0
            meta = _ffprobe_video(clip)
            ok = meta and meta["width"] == 1080 and meta["height"] == 1920
            report.add(
                "Clip 9:16 + bypass",
                "Pilar 2",
                ok and clip.exists(),
                dt,
                f"{meta}" if meta else "ffprobe falhou",
            )
            pipeline_clip = clip
        except Exception as e:
            report.add("Clip 9:16 + bypass", "Pilar 2", False, time.perf_counter() - t0, str(e)[:200])
            pipeline_clip = None

        # Render
        if pipeline_clip:
            t0 = time.perf_counter()
            try:
                from src.models.job import JobRecord, JobStatus
                from src.pipeline.render_job import run_post_approval

                ass = res.get("subtitles_ass", "")
                job = JobRecord(
                    job_id="audit01",
                    status=JobStatus.PENDING_APPROVAL,
                    niche="curiosidades",
                    clip_path=_rel_path(pipeline_clip),
                    hook_text="teste",
                    climax_reason="auditoria",
                    reaction_script="Comentario de teste para auditoria.",
                    metadata={"subtitles_ass": _rel_path(ass) if ass else ""},
                )
                job = run_post_approval(job)
                final = ROOT / (job.output_path or "")
                meta = _ffprobe_video(final)
                ok = meta and meta["width"] == 1080 and meta["height"] == 1920
                report.add(
                    "Render final PiP",
                    "Pilar 3",
                    ok and final.exists(),
                    time.perf_counter() - t0,
                    str(job.output_path),
                )
            except Exception as e:
                report.add("Render final PiP", "Pilar 3", False, time.perf_counter() - t0, str(e)[:200])

    # API
    try:
        import httpx

        r = httpx.get(f"http://{settings.api_host}:{settings.api_port}/health", timeout=3)
        report.add("API /health", "Pilar 4", r.status_code == 200, detail=r.json().get("status", ""))
    except Exception as e:
        report.add("API /health", "Pilar 4", False, detail=str(e)[:120])

    # Jobs DB
    jobs_file = ROOT / "storage" / "jobs_db.json"
    report.add("Persistencia jobs", "Pilar 4", jobs_file.exists(), detail=str(jobs_file))

    return report.print_report()


if __name__ == "__main__":
    skip = "--skip-download" in sys.argv
    sys.exit(run_audit(skip_download=skip))
