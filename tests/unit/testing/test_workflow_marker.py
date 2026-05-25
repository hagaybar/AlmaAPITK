from almaapitk.testing import workflow


def test_marker_attaches_metadata():
    @workflow(name="demo", environment="SANDBOX", readonly=True)
    def some_workflow(alma):
        ...

    assert some_workflow.__alma_workflow__ == {
        "name": "demo",
        "environment": "SANDBOX",
        "readonly": True,
    }
