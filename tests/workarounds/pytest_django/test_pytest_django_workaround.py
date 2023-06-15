def test_settings_mutation_is_worked_around(django_db_setup, db):
    from django.conf import settings

    databases = settings.DATABASES

    test_db_name: str = databases["default"]["NAME"]
    assert (
        test_db_name.count("test_") == 1
    ), f"Counted {test_db_name.count('test_')} occurences of 'test_' in {test_db_name}"
    assert (
        test_db_name.count("_tox") == 0
    ), f"Counted {test_db_name.count('_tox')} occurences of '_tox' in {test_db_name}"
