from omniscia.core.wakeword import extract_after_wake_word


def test_wakeword_activates_at_start():
    ok, cmd = extract_after_wake_word("void abre o chrome", wake_word="void", mode="prefix")
    assert ok is True
    assert cmd == "abre o chrome"


def test_wakeword_activates_with_greeting_prefix():
    ok, cmd = extract_after_wake_word("Ei void, abre o explorer", wake_word="void", mode="prefix")
    assert ok is True
    assert cmd.lower().startswith("abre")


def test_wakeword_activates_with_article_prefix():
    ok, cmd = extract_after_wake_word("o void", wake_word="void", mode="prefix")
    assert ok is True
    assert cmd == ""


def test_wakeword_does_not_activate_mid_sentence():
    ok, cmd = extract_after_wake_word("como evitar void em C?", wake_word="void", mode="prefix")
    assert ok is False
    assert cmd == ""


def test_wakeword_activates_mid_sentence_in_anywhere_mode():
    ok, cmd = extract_after_wake_word("como evitar void em C?", wake_word="void", mode="anywhere")
    assert ok is True
    assert cmd.lower().startswith("em")


def test_wakeword_does_not_activate_in_code_context_in_smart_mode():
    ok, cmd = extract_after_wake_word("como evitar void em C?", wake_word="void", mode="smart")
    assert ok is False
    assert cmd == ""


def test_wakeword_activates_mid_sentence_in_smart_mode_when_not_code_context():
    ok, cmd = extract_after_wake_word("pode me ajudar void abre o explorer", wake_word="void", mode="smart")
    assert ok is True
    assert cmd.lower().startswith("abre")


def test_wakeword_case_insensitive():
    ok, cmd = extract_after_wake_word("OLÁ VOID: tudo bem?", wake_word="void", mode="prefix")
    assert ok is True
    assert cmd.lower().startswith("tudo")
