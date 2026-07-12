from __future__ import annotations
import os, re
class EnvLeakError(Exception): pass
_SAFE={'PATH','HOME','LANG','TZ'}
_SECRET=re.compile(r'^(AWS_|GITHUB_|GH_|OPENAI_|ANTHROPIC_|.*TOKEN|.*SECRET|.*KEY$|.*PASSWORD)')
def build_env(role, allowlist, extra):
    env={}
    for name,value in allowlist.items():
        if value is None:
            if name in _SAFE and name in os.environ: env[name]=os.environ[name]
        else: env[name]=str(value)
    env.update({str(k):str(v) for k,v in extra.items()})
    for name in env:
        if _SECRET.match(name): raise EnvLeakError(name)
    return env
def redact(text, env):
    for value in env.values():
        if len(value)>=32: text=text.replace(value,'[redacted]')
    return text
