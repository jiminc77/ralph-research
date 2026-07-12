import pytest

from ralph_core.resolver import ModelResolver, ResolverError
from tests.fakes.fake_seams import FakeCatalog


def test_resolves_and_falls_back():
    result = ModelResolver(
        {
            "builder": {
                "alias": "missing",
                "fallback_chain": ["claude-fable-5"],
            },
            "reviewer": {"alias": "claude-opus-4-8"},
        },
        FakeCatalog(),
    ).resolve_all()
    assert result["builder"]["model_id"] == "model-fable"


def test_reviewer_is_blocking():
    with pytest.raises(ResolverError, match="claude-opus-4-8"):
        ModelResolver({"reviewer": {"alias": "claude-opus-4-8"}}, FakeCatalog({})).resolve_all()


def test_unresolved_reviewer_lists_alias_and_role():
    with pytest.raises(ResolverError) as exc_info:
        ModelResolver({"reviewer": {"alias": "claude-opus-4-8"}}, FakeCatalog({})).resolve_all()
    assert "claude-opus-4-8" in str(exc_info.value)
    assert "reviewer" in str(exc_info.value)


def test_fallback_chain_order_respected():
    class RecordingCatalog:
        def __init__(self):
            self.aliases = []

        def resolve(self, alias):
            self.aliases.append(alias)
            return "selected" if alias == "second" else None

    catalog = RecordingCatalog()
    ModelResolver(
        {"builder": {"alias": "first", "fallback_chain": ["second", "third"]}},
        catalog,
    ).resolve_all()
    assert catalog.aliases == ["first", "second"]
