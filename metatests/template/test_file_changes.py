from .file_changes import SomeClass, some_func


def test_file_function_change():
    """
    This test uses a function that has the return value changed.

    Should pass
    """
    assert some_func() == "foo modified"


def test_class_method_change():
    """
    This test uses a method that has the return value changed.

    Should pass
    """
    assert SomeClass().some_method() == "bar modified"


def test_staticmethod_change():
    """
    This test uses a static method that has the return value changed.

    Should pass
    """
    assert SomeClass.some_static_method() == "moo modified"
