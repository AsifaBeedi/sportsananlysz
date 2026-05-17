from .config import AppConfig
from .profiles import get_sport_profile, supported_sports

__all__ = ["AppConfig", "get_sport_profile", "run_video_session", "supported_sports"]


def __getattr__(name: str):
    if name == "run_video_session":
        from .pipeline import run_video_session

        return run_video_session
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
