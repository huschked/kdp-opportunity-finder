from pathlib import Path

from streamlit.testing.v1 import AppTest

from config.settings import get_settings


ROOT = Path(__file__).resolve().parents[1]


def test_app_dashboard_and_sample_load(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "streamlit_test.db"
    monkeypatch.setenv("KDP_DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    app = AppTest.from_file(ROOT / "app.py", default_timeout=10).run()
    assert not app.exception
    assert app.title[0].value == "Dashboard"
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].value == "3"

    app.switch_page("app_pages/research.py").run()
    assert not app.exception
    assert app.title[0].value == "Research"
    for task in ("Add or edit book", "Import books", "Import reviews"):
        app.selectbox(key="research_task").set_value(task).run()
        assert not app.exception

    app.selectbox(key="research_task").set_value("Analyze reviews").run()
    assert not app.exception

    app.switch_page("app_pages/niche_detail.py").run()
    assert not app.exception
    assert app.title[0].value == "Niche detail"
    for view in ("Decision", "Opportunity report", "Competitors", "Reviews", "Pain points", "Praise", "Analysis history"):
        app.selectbox(key="detail_view").set_value(view).run()
        assert not app.exception

    app.selectbox(key="detail_view").set_value("Decision").run()
    next(button for button in app.button if button.label == "Calculate a new snapshot").click().run()
    assert not app.exception
    assert len(app.metric) >= 4

    app.switch_page("app_pages/report.py").run()
    assert not app.exception
    assert app.title[0].value == "Opportunity report"
    assert app.selectbox(key="report_niche")
    assert app.download_button

    app.switch_page("app_pages/concept.py").run()
    assert not app.exception
    assert app.title[0].value == "Book specification"
    assert app.selectbox(key="concept_niche")
    next(button for button in app.button if button.label == "Generate new specification").click().run()
    assert not app.exception
    assert len(app.metric) >= 4
    assert app.download_button

    app.switch_page("app_pages/compare.py").run()
    assert not app.exception
    assert app.title[0].value == "Compare"
    comparison_picker = app.multiselect(key="comparison_niches")
    assert len(comparison_picker.value) == 3
    comparison_picker.set_value(comparison_picker.value[:2]).run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 2
    assert app.warning or app.success
