import template_project


def test_package_imports_with_version():
    assert template_project.__version__ == "0.1.0"
