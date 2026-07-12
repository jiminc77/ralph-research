from __future__ import annotations
import shlex

from pathlib import Path


class PathDenied(Exception):
    pass


class CommandDenied(Exception):
    pass


class PathGuard:
    def __init__(self, allowed_roots, denied_roots):
        self.allowed_roots = [Path(root).resolve() for root in allowed_roots]
        self.denied_roots = [Path(root).resolve() for root in denied_roots]

    @staticmethod
    def _inside(path, root):
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def check_path(self, path):
        resolved = Path(path).resolve()
        return (
            any(self._inside(resolved, root) for root in self.allowed_roots)
            and not any(self._inside(resolved, root) for root in self.denied_roots)
        )

    def check_tool_call(self, tool, args):
        argv = [str(arg) for arg in args]

        def contains_git_push(tokens):
            words = [token for token in tokens if not token.startswith("-")]
            for index, word in enumerate(words):
                if word != "git":
                    continue
                for candidate in words[index + 1 :]:
                    if "/" in candidate or candidate.startswith(".") or "=" in candidate:
                        continue
                    if candidate == "push":
                        return True
                    break
            return False

        token_groups = [argv]
        for arg in argv:
            if any(character.isspace() for character in arg):
                try:
                    token_groups.append(shlex.split(arg, posix=True))
                except ValueError:
                    token_groups.append(arg.split())
        if any(contains_git_push(tokens) for tokens in token_groups):
            raise CommandDenied("git push denied")
        for arg in argv:
            if "/" in arg or arg.startswith("."):
                if not self.check_path(arg):
                    raise PathDenied(arg)
        return True
