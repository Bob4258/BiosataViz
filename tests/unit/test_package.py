def test_package_exposes_version():
    import biostatviz

    assert biostatviz.__version__ == "0.1.0"
