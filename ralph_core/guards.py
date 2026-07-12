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
            value_options = {"-C", "-c", "--git-dir", "--work-tree", "--exec-path"}
            index = 0
            while index < len(tokens):
                if tokens[index] != "git":
                    index += 1
                    continue
                index += 1
                while index < len(tokens) and tokens[index].startswith("-"):
                    option = tokens[index]
                    index += 2 if option in value_options else 1
                if index < len(tokens) and tokens[index] == "push":
                    return True
            return False

        def split_separators(tokens):
            groups = []
            for token in tokens:
                normalized = token.replace("&&", " ").replace("||", " ")
                normalized = normalized.replace(";", " ").replace("|", " ")
                groups.extend(normalized.split())
            return groups

        token_groups = [split_separators(argv)]
        for arg in argv:
            if any(character.isspace() for character in arg):
                try:
                    token_groups.append(split_separators(shlex.split(arg, posix=True)))
                except ValueError:
                    token_groups.append(split_separators(arg.split()))
        if any(contains_git_push(tokens) for tokens in token_groups):
            raise CommandDenied("git push denied")
        for arg in argv:
            if "/" in arg or arg.startswith("."):
                if not self.check_path(arg):
                    raise PathDenied(arg)
        return True
