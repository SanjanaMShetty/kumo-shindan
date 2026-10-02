from kumoshindan.config import Settings


def test_namespaces_are_parsed_and_trimmed():
    settings = Settings(_env_file=None, allowed_namespaces="demo, staging ,")
    assert settings.namespaces == ["demo", "staging"]


def test_defaults_are_safe():
    settings = Settings(_env_file=None)
    assert settings.max_steps <= 10
    assert settings.max_concurrent_investigations >= 1
