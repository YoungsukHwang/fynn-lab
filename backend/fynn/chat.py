"""Terminal chat with one or both bots.

    python -m fynn.chat --persona rebuilder            # both bots, same message
    python -m fynn.chat --persona rebuilder --bot after
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import anthropic

from fynn.bots import Bot, BotReply, build_bots
from fynn.llm import AnthropicLLM, LLM, LLMError
from fynn.personas import load_personas
from fynn.skills import SkillLibrary


def _print_reply(reply: BotReply) -> None:
    routing = reply.routing
    label = "agent" if routing.strategy == "single_agent" else "skills"
    picked = ", ".join(routing.selected) or "(none)"
    carried = f" + carried: {', '.join(routing.carried)}" if routing.carried else ""
    usage = reply.usage
    print(f"\n[{reply.bot.upper()}] {label}: {picked}{carried}  ({reply.model})")
    if routing.error:
        fallback = "with carried skills only" if routing.carried else "without topic guidance"
        print(f"  router error, answered {fallback}: {routing.error}")
    else:
        print(f"  router reason: {routing.reason}")
    print(
        f"  tokens in/out: {usage.input_tokens}/{usage.output_tokens} "
        f"(cache read {usage.cache_read_input_tokens}, cache write {usage.cache_creation_input_tokens})\n"
    )
    print(reply.text)


def run(persona_id: str, bot_names: list[str], llm: LLM, library: SkillLibrary) -> None:
    persona = load_personas()[persona_id]
    bots: dict[str, Bot] = build_bots(llm, library)  # type: ignore[assignment]
    histories: dict[str, list[dict[str, str]]] = {name: [] for name in bot_names}
    last_picks: dict[str, list[str]] = {name: [] for name in bot_names}

    print(f"Persona: {persona.name} ({persona.id}): {persona.summary}")
    print("Type a message, or 'quit' to exit.")
    while True:
        try:
            message = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if message.lower() in {"quit", "exit"}:
            break
        if not message:
            continue
        for name in bot_names:
            history = histories[name]
            history.append({"role": "user", "content": message})
            try:
                reply = bots[name].reply(persona, history, carry_skills=last_picks[name])
            except (LLMError, anthropic.APIError) as exc:
                history.pop()  # keep the history valid so the conversation can go on
                print(f"\n[{name.upper()}] error, message not answered: {exc}")
                continue
            except KeyboardInterrupt:
                history.pop()
                print(f"\n[{name.upper()}] interrupted")
                continue
            history.append({"role": "assistant", "content": reply.text})
            if name == "after":  # only the skill architecture carries skills between turns
                last_picks[name] = reply.routing.selected
            _print_reply(reply)


def _has_credentials() -> bool:
    # fynn.config has already loaded backend/.env. An `ant auth login` profile also works.
    config_dir = Path(os.environ.get("ANTHROPIC_CONFIG_DIR", "~/.config/anthropic")).expanduser()
    return any(os.environ.get(v) for v in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")) or config_dir.exists()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the before/after credit coach bots.")
    parser.add_argument("--persona", default="rebuilder", choices=sorted(load_personas()))
    parser.add_argument("--bot", choices=["before", "after", "both"], default="both")
    args = parser.parse_args()
    if not _has_credentials():
        parser.error("no Anthropic credentials found: add ANTHROPIC_API_KEY to backend/.env")
    names = ["before", "after"] if args.bot == "both" else [args.bot]
    run(args.persona, names, AnthropicLLM(), SkillLibrary.load())


if __name__ == "__main__":
    main()
