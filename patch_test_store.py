with open('tests/test_store.py', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace(
    'with pytest.raises(RuntimeError):\n        repo.get_settings(s)',
    'defaults = repo.get_settings(s)\n    assert defaults.r_max == 50.0'
)

with open('tests/test_store.py', 'w', encoding='utf-8') as f:
    f.write(c)
