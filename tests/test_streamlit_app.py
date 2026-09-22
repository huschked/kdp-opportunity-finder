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

    for page_path, page_title in (
        ("app_pages/niche_detail.py", "Niche detail"),
        ("app_pages/report.py", "Opportunity report"),
        ("app_pages/concept.py", "Book specification"),
        ("app_pages/compare.py", "Compare"),
        ("app_pages/pipeline.py", "Pipeline"),
        ("app_pages/exports.py", "Exports"),
    ):
        app.switch_page(page_path).run()
        assert not app.exception
        assert app.title[0].value == page_title
        assert app.info

    app.switch_page("app_pages/dashboard.py").run()
    next(button for button in app.button if button.label == "Load synthetic sample").click().run()
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

    app.switch_page("app_pages/pipeline.py").run()
    assert not app.exception
    assert app.title[0].value == "Pipeline"
    assert len(app.metric) == 4
    assert len(app.dataframe[0].value) == 3

    app.multiselect(key="pipeline_status_filter").set_value(["promising"]).run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 1
    app.multiselect(key="pipeline_status_filter").set_value([]).run()
    assert not app.exception

    niche_id = app.selectbox(key="pipeline_move_niche").value
    app.selectbox(key=f"pipeline_new_status_{niche_id}").set_value("validation")
    app.text_area(key=f"pipeline_status_rationale_{niche_id}").set_value(
        "Ready for a human validation pass."
    )
    next(button for button in app.button if button.label == "Save status change").click().run()
    assert not app.exception
    assert app.success
    assert len(app.dataframe) == 2

    app.switch_page("app_pages/exports.py").run()
    assert not app.exception
    assert app.title[0].value == "Exports"
    assert app.segmented_control(key="export_dataset").value == "decisions"
    assert app.selectbox(key="export_decision_scope")
    assert len(app.dataframe[0].value) == 3
    assert {button.label for button in app.download_button} == {
        "Download CSV",
        "Download JSON",
    }

    app.segmented_control(key="export_dataset").set_value("books").run()
    assert not app.exception
    assert app.selectbox(key="export_books_niche")
    assert len(app.dataframe[0].value) == 10
    assert len(app.download_button) == 2

    app.segmented_control(key="export_dataset").set_value("reviews").run()
    assert not app.exception
    assert app.selectbox(key="export_reviews_niche")
    assert len(app.dataframe[0].value) == 60
    assert len(app.download_button) == 2
