"""Run-scoped names and rendering for executable estate assets."""
import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex


@dataclass(frozen=True)
class RunConfig:
    token: str = "sfx1119"

    def __post_init__(self):
        if not re.fullmatch(r"sfx-?[a-z0-9]+(?:-[a-z0-9]+)*", self.token):
            raise ValueError("RUN_TOKEN must be a lowercase sfx-prefixed identifier")

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("RUN_TOKEN", os.environ.get("SNOWFLAKE_RUN_TOKEN", "sfx1119")))

    @property
    def suffix(self):
        return self.token[3:].lstrip("-")

    @property
    def database(self):
        return "SFX_" + self.suffix.upper().replace("-", "_")

    @property
    def before_namespace(self):
        return "sfx-" + self.suffix + "-before"

    @property
    def after_namespace(self):
        return "sfx-" + self.suffix + "-after"

    def environment(self):
        return {"RUN_TOKEN": self.token, "RUN_DATABASE": self.database,
                "RUN_BEFORE_NAMESPACE": self.before_namespace,
                "RUN_AFTER_NAMESPACE": self.after_namespace}

    def render(self, text):
        if not isinstance(text, str):
            return text
        values = {"__RUN_TOKEN__": self.token, "__RUN_DATABASE__": self.database,
                  "__BEFORE_NAMESPACE__": self.before_namespace,
                  "__AFTER_NAMESPACE__": self.after_namespace}
        for marker, value in values.items():
            text = text.replace(marker, value)
        text = re.sub(r"sfx-d[0-9]+-before", self.before_namespace, text)
        text = re.sub(r"sfx-d[0-9]+-after", self.after_namespace, text)
        text = re.sub(r"sfx-d[0-9]+", self.token, text)
        return re.sub(r"SFX_D[0-9]+(?:_AFTER)?", self.database, text)


def render(text):
    return RunConfig.from_env().render(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["env", "render"])
    parser.add_argument("path", nargs="?", type=Path)
    args = parser.parse_args()
    config = RunConfig.from_env()
    if args.command == "env":
        for key, value in config.environment().items():
            print(f"export {key}={shlex.quote(value)}")
    else:
        if args.path is None:
            parser.error("render requires an asset path")
        print(config.render(args.path.read_text()), end="")


if __name__ == "__main__":
    main()
