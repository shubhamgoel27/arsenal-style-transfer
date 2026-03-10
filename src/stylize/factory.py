"""Factory for creating style transfer engine instances."""

from .engine import StyleEngine


def create_engine(backend: str = "local_sd", **kwargs) -> StyleEngine:
    """Create a style engine by backend name.

    Args:
        backend: One of "local_sd", "gemini", "replicate".
        **kwargs: Passed to the engine constructor.
    """
    if backend == "local_sd":
        from .local_sd import LocalSDEngine
        return LocalSDEngine(**kwargs)
    elif backend == "gemini":
        from .gemini import GeminiEngine
        return GeminiEngine(**kwargs)
    else:
        raise ValueError(
            f"Unknown backend '{backend}'. Available: local_sd, gemini"
        )
