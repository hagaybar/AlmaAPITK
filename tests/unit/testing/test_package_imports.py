def test_testing_package_importable():
    import almaapitk.testing as t

    assert hasattr(t, "__all__")
