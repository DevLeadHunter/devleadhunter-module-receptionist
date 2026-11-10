"""How the core's visit tracking reads the receptionist's video page (/va): its events, their labels and scores."""

from __future__ import annotations

# The receptionist's video page (/va) emits the site video's events under its own prefix.
VIDEO_PAGE_EVENT_PREFIX: str = "assistant_video_"

# The prospect timeline's label of each event of the receptionist's video page.
VIDEO_PAGE_EVENT_LABELS: dict[str, str] = {
    "assistant_video_play": "Lecture de la vidéo réceptionniste",
    "assistant_video_resume": "Reprise de la vidéo réceptionniste",
    "assistant_video_pause": "Vidéo réceptionniste mise en pause",
    "assistant_video_replay": "A revu la vidéo réceptionniste",
    "assistant_video_progress": "Vidéo réceptionniste regardée en partie",
    "assistant_video_complete": "Vidéo réceptionniste regardée en entier",
    "assistant_video_watch_time": "Temps de visionnage de la vidéo réceptionniste",
    "assistant_video_seek": "A avancé / reculé dans la vidéo réceptionniste",
    "assistant_video_fullscreen": "Vidéo réceptionniste en plein écran",
    "assistant_video_mute": "A coupé / remis le son de la vidéo réceptionniste",
    "assistant_video_cta_click": "Clic vers la démo depuis la vidéo réceptionniste",
}

# The receptionist's video events that score as the site video's (both mean the prospect watched).
VIDEO_PAGE_LEAD_SCORE_ALIASES: dict[str, str] = {
    "assistant_video_play": "demo_video_play",
    "assistant_video_complete": "demo_video_complete",
    "assistant_video_replay": "demo_video_replay",
    "assistant_video_fullscreen": "demo_video_fullscreen",
    "assistant_video_progress": "demo_video_progress",
    "assistant_video_watch_time": "demo_video_watch_time",
}

# The receptionist's events the behaviour queries read in PostHog, along with the sites'.
VIDEO_PAGE_POSTHOG_EVENTS: tuple[str, ...] = (
    "assistant_video_play",
    "assistant_video_resume",
    "assistant_video_pause",
    "assistant_video_replay",
    "assistant_video_progress",
    "assistant_video_complete",
    "assistant_video_watch_time",
    "assistant_video_seek",
    "assistant_video_fullscreen",
    "assistant_video_mute",
    "assistant_video_cta_click",
)
