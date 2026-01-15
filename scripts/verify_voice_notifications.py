#!/usr/bin/env python
import argparse
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def check_voice_flags(config: dict) -> dict:
    voice = config.get("voice") or {}
    return {
        "voice.moment_complete_enabled": bool(voice.get("moment_complete_enabled", False)),
        "voice.agent_group_complete_enabled": bool(voice.get("agent_group_complete_enabled", False)),
        "voice.customer_group_complete_enabled": bool(voice.get("customer_group_complete_enabled", False)),
    }


def check_pyttsx3() -> tuple[bool, str]:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        engine.stop()
        return True, f"ok (voices={len(voices)})"
    except Exception as exc:
        return False, f"failed: {exc}"


def _format_text(template: str, remaining: int, code: str, fallback: str) -> str:
    try:
        return template.format(code=code or "", remaining=remaining)
    except Exception:
        return fallback.format(code=code or "", remaining=remaining)


def speak_sample(config: dict) -> None:
    from services.voice_notifier import get_voice_notifier

    voice_cfg = config.get("voice") or {}
    moment_template = voice_cfg.get("moment_complete_text") or "Moment complete, remaining {remaining}."
    agent_template = voice_cfg.get("agent_group_complete_text") or "Agent group complete, remaining {remaining}."
    customer_template = voice_cfg.get("customer_group_complete_text") or "Customer group complete, remaining {remaining}."

    texts = [
        _format_text(moment_template, remaining=1, code="TEST", fallback="Moment complete, remaining {remaining}."),
        _format_text(agent_template, remaining=1, code="TEST", fallback="Agent group complete, remaining {remaining}."),
        _format_text(customer_template, remaining=1, code="TEST", fallback="Customer group complete, remaining {remaining}."),
    ]

    notifier = get_voice_notifier()
    for text in texts:
        # Use the notifier's sync path so the process doesn't exit before audio plays.
        notifier._speak_sync(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify voice notification config and TTS availability.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.yaml (default: repo root/config.yaml)",
    )
    parser.add_argument(
        "--speak",
        action="store_true",
        help="Play sample voice notifications (will speak audio).",
    )
    args = parser.parse_args()

    config_path = args.config or (REPO_ROOT / "config.yaml")

    try:
        config = load_config(config_path)
    except Exception as exc:
        print(f"config: failed to load ({exc})")
        return 1

    flags = check_voice_flags(config)
    for key, value in flags.items():
        print(f"{key}: {value}")

    tts_ok, tts_msg = check_pyttsx3()
    print(f"pyttsx3: {tts_msg}")

    if args.speak:
        if not tts_ok:
            print("speak: skipped (pyttsx3 not available)")
            return 1
        speak_sample(config)
        print("speak: finished sample notifications")

    all_ok = all(flags.values()) and tts_ok
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
