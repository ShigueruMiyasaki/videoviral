"""Monta a linha do tempo de falas a partir do nível de interação.

As falas de referência funcionam sem LLM, para o dry-run ser testável.
Quando houver transcrição real, o mesmo formato de beats é o contrato
que o render vai consumir.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.interaction.levels import LEVELS


class AvatarState(str, Enum):
    LISTENING = "listening"
    SPEAKING = "speaking"


class Beat(BaseModel):
    t_start: float
    t_end: float
    state: AvatarState
    pause_source: bool = False
    line: str = ""
    purpose: str


class ScriptPlan(BaseModel):
    level: int
    level_name: str
    niche: str
    tone: str
    layout: str
    duration_sec: float
    hook_line: str
    spoken_script: str
    speak_sec: float
    beats: list[Beat] = Field(default_factory=list)


def _window(duration: float) -> float:
    if duration <= 0:
        return 30.0
    return max(15.0, min(60.0, duration))


def _clip_beat(start: float, end: float, duration: float) -> tuple[float, float] | None:
    start = max(0.0, min(start, duration))
    end = max(start, min(end, duration))
    if end - start < 0.35:
        return None
    return round(start, 2), round(end, 2)


def _hook(level: int, niche: str, tone: str, hook_text: str) -> str:
    if hook_text.strip():
        return hook_text.strip()
    openers = {
        "sarcastico": "Sério que isso passou batido",
        "humoristico": "Calma, que essa parte é boa",
        "informativo": "O ponto que importa está aqui",
    }
    opener = openers.get(tone, openers["informativo"])
    if level >= 5:
        return f"Em três segundos: {opener.lower()} em {niche}."
    if level == 1:
        return f"Olha isso de {niche}."
    return f"{opener} — {niche}."


def _comment(level: int, niche: str, tone: str, purpose: str) -> str:
    if purpose == "closer":
        return f"Se isso mudou sua leitura de {niche}, segue para o próximo corte."
    if purpose == "rebuttal":
        if tone == "sarcastico":
            return f"Essa conclusão de {niche} não fecha. Falta o outro lado."
        return f"Discordo desse trecho: em {niche} o dado não sustenta essa frase."
    if purpose == "narration":
        return f"Enquanto isso rola, repara no que ninguém destaca sobre {niche}."
    if level <= 2:
        return f"É exatamente nesse segundo que {niche} vira assunto."
    return f"Pausa aqui. Esse é o momento que explica o resto de {niche}."


def _add(
    beats: list[Beat],
    duration: float,
    start: float,
    end: float,
    state: AvatarState,
    purpose: str,
    line: str = "",
    pause: bool = False,
) -> None:
    span = _clip_beat(start, end, duration)
    if span is None:
        return
    beats.append(
        Beat(
            t_start=span[0],
            t_end=span[1],
            state=state,
            pause_source=pause and state == AvatarState.SPEAKING,
            line=line if state == AvatarState.SPEAKING else "",
            purpose=purpose,
        )
    )


def _timeline(level: int, duration: float, niche: str, tone: str, hook: str) -> list[Beat]:
    beats: list[Beat] = []
    comment = lambda purpose: _comment(level, niche, tone, purpose)  # noqa: E731

    if level == 1:
        _add(beats, duration, 0, 2.6, AvatarState.SPEAKING, "hook", hook)
        _add(beats, duration, 2.6, duration - 3, AvatarState.LISTENING, "listen")
        _add(beats, duration, duration - 3, duration, AvatarState.SPEAKING, "closer", comment("closer"))
        return beats

    if level == 2:
        mid = duration * 0.45
        _add(beats, duration, 0, 3, AvatarState.SPEAKING, "hook", hook)
        _add(beats, duration, 3, mid, AvatarState.LISTENING, "listen")
        _add(beats, duration, mid, mid + 3.5, AvatarState.SPEAKING, "reaction", comment("reaction"))
        _add(beats, duration, mid + 3.5, duration - 3, AvatarState.LISTENING, "listen")
        _add(beats, duration, duration - 3, duration, AvatarState.SPEAKING, "closer", comment("closer"))
        return beats

    if level == 3:
        first = duration * 0.38
        second = duration * 0.72
        _add(beats, duration, 0, 3, AvatarState.SPEAKING, "hook", hook, pause=True)
        _add(beats, duration, 3, first, AvatarState.LISTENING, "listen")
        _add(beats, duration, first, first + 4, AvatarState.SPEAKING, "reaction", comment("reaction"), pause=True)
        _add(beats, duration, first + 4, second, AvatarState.LISTENING, "listen")
        _add(beats, duration, second, second + 4, AvatarState.SPEAKING, "reaction", comment("reaction"), pause=True)
        _add(beats, duration, second + 4, duration, AvatarState.LISTENING, "listen")
        return beats

    if level == 4:
        _add(beats, duration, 0, 3, AvatarState.SPEAKING, "hook", hook, pause=True)
        _add(beats, duration, 3, duration * 0.35, AvatarState.LISTENING, "claim")
        _add(
            beats, duration, duration * 0.35, duration * 0.35 + 4.5,
            AvatarState.SPEAKING, "rebuttal", comment("rebuttal"), pause=True,
        )
        _add(beats, duration, duration * 0.35 + 4.5, duration * 0.7, AvatarState.LISTENING, "claim")
        _add(
            beats, duration, duration * 0.7, duration * 0.7 + 4,
            AvatarState.SPEAKING, "rebuttal", comment("rebuttal"), pause=True,
        )
        _add(beats, duration, duration * 0.7 + 4, duration, AvatarState.SPEAKING, "closer", comment("closer"))
        return beats

    # Nível 5 — narra por cima, gancho preso nos 3 primeiros segundos.
    _add(beats, duration, 0, 3, AvatarState.SPEAKING, "hook", hook)
    cursor = 3.0
    narration = 0
    while cursor + 6 < duration - 3.5:
        _add(beats, duration, cursor, cursor + 3, AvatarState.LISTENING, "listen")
        line = comment("rebuttal") if narration == 1 else comment("narration")
        purpose = "rebuttal" if narration == 1 else "narration"
        _add(beats, duration, cursor + 3, cursor + 6.5, AvatarState.SPEAKING, purpose, line)
        cursor += 6.5
        narration += 1
    _add(beats, duration, cursor, duration - 3.2, AvatarState.LISTENING, "listen")
    _add(beats, duration, duration - 3.2, duration, AvatarState.SPEAKING, "closer", comment("closer"))
    return beats


def build_plan(
    *,
    level: int,
    niche: str,
    tone: str,
    layout: str,
    duration_sec: float = 30.0,
    hook_text: str = "",
    climax_reason: str = "",
) -> ScriptPlan:
    """Gera o plano de beats. `climax_reason` entra na fala do meio quando existe."""
    level = min(5, max(1, int(level)))
    duration = _window(duration_sec)
    spec = LEVELS[level]
    hook = _hook(level, niche, tone, hook_text)
    beats = _timeline(level, duration, niche, tone, hook)
    if climax_reason.strip():
        for beat in beats:
            if beat.purpose == "reaction" and beat.line:
                beat.line = f"{beat.line} {climax_reason.strip()}"
                break
    spoken = " ".join(beat.line.strip() for beat in beats if beat.line.strip())
    speak_sec = sum(beat.t_end - beat.t_start for beat in beats if beat.state == AvatarState.SPEAKING)
    return ScriptPlan(
        level=level,
        level_name=spec.name,
        niche=niche,
        tone=tone,
        layout=layout,
        duration_sec=duration,
        hook_line=hook,
        spoken_script=spoken,
        speak_sec=round(speak_sec, 2),
        beats=beats,
    )
