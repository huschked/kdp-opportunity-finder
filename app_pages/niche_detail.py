"""Competitor summaries and searchable review evidence."""

from datetime import date

import pandas as pd
import streamlit as st

from analysis.market import summarize_competitors
from db.database import session_scope
from db.repositories import BookRepository, NicheRepository, ReviewRepository
from ui.evidence_views import render_analysis_history, render_pain_points, render_praise
from ui.decision_views import render_decision
from ui.report_views import render_opportunity_report


st.caption("Inspect observable competitor data and the source reviews behind later analysis.")

with session_scope() as session:
    niches = NicheRepository(session).list_all()

if not niches:
    st.info("Create a niche before opening its detail view.")
    st.stop()

niches_by_id = {niche.id: niche for niche in niches}
niche_id = st.selectbox(
    "Niche",
    list(niches_by_id),
    format_func=lambda value: niches_by_id[value].name,
    key="detail_niche",
    bind="query-params",
)
view = st.selectbox(
    "View", ("Decision", "Opportunity report", "Competitors", "Reviews", "Pain points", "Praise", "Analysis history"), index=0, key="detail_view"
)

with session_scope() as session:
    book_repository = BookRepository(session)
    books = book_repository.list_by_niche(niche_id)
    competitor_rows = book_repository.rows_by_niche(niche_id)

if view == "Decision":
    render_decision(niche_id)
elif view == "Opportunity report":
    render_opportunity_report(niche_id)
elif view == "Competitors":
    st.subheader("Competitor evidence")
    summary = summarize_competitors(competitor_rows)
    metrics = st.columns(3)
    metrics[0].metric("Books", summary["book_count"])
    metrics[1].metric("Median price", f"${summary['median_price']:.2f}" if summary["median_price"] is not None else "Missing")
    metrics[2].metric("Median rating", f"{summary['median_rating']:.2f}" if summary["median_rating"] is not None else "Missing")
    metrics = st.columns(3)
    metrics[0].metric("Median reviews", f"{summary['median_review_count']:,.0f}" if summary["median_review_count"] is not None else "Missing")
    metrics[1].metric("Median pages", f"{summary['median_page_count']:,.0f}" if summary["median_page_count"] is not None else "Missing")
    metrics[2].metric("Top-three share", f"{summary['top_three_review_share']:.1f}%" if summary["top_three_review_share"] is not None else "Missing")

    search = st.text_input("Search title or author", key="competitor_search", placeholder="Filter competitors")
    formats = sorted({row["format"] for row in competitor_rows if row["format"]})
    selected_formats = st.multiselect("Formats", formats, key="competitor_formats")
    filtered = competitor_rows
    if search.strip():
        term = search.casefold().strip()
        filtered = [
            row for row in filtered
            if term in str(row["title"]).casefold() or term in str(row["author"] or "").casefold()
        ]
    if selected_formats:
        filtered = [row for row in filtered if row["format"] in selected_formats]

    if filtered:
        frame = pd.DataFrame(filtered).rename(columns={
            "title": "Title",
            "author": "Author",
            "price": "Price",
            "rating": "Rating",
            "review_count": "Reviews",
            "best_seller_rank": "BSR",
            "page_count": "Pages",
            "publication_date": "Published",
            "format": "Format",
            "publisher": "Publisher",
            "source_identifier": "Source identifier",
        }).drop(columns=["id"])
        st.dataframe(
            frame,
            hide_index=True,
            key="competitor_table",
            column_config={
                "Title": st.column_config.TextColumn(pinned=True),
                "Price": st.column_config.NumberColumn(format="dollar"),
                "Rating": st.column_config.NumberColumn(format="%.1f", min_value=0, max_value=5),
                "Reviews": st.column_config.NumberColumn(format="localized"),
                "BSR": st.column_config.NumberColumn(format="localized"),
                "Pages": st.column_config.NumberColumn(format="localized"),
                "Published": st.column_config.DateColumn(format="MMM DD, YYYY"),
            },
        )
        chart_rows = [
            {"Title": row["title"], "Reviews": row["review_count"]}
            for row in filtered if row["review_count"] is not None
        ]
        if chart_rows:
            st.subheader("Where competitor attention is concentrated")
            st.bar_chart(pd.DataFrame(chart_rows), x="Title", y="Reviews", horizontal=True)
    else:
        st.info("No competitors match the current filters.")
elif view == "Reviews":
    st.subheader("Review evidence")
    book_options = {book.id: book.title for book in books}
    with session_scope() as session:
        filter_options = ReviewRepository(session).analysis_filter_options(niche_id)
    pain_options = {item.id: item.canonical_name for item in filter_options["pain_points"]}
    with st.form("review_filters", border=False):
        query = st.text_input("Search review title or text", key="review_query")
        book_id = st.selectbox(
            "Book", [None, *book_options], format_func=lambda value: "All books" if value is None else book_options[value]
        )
        ratings = st.multiselect("Star ratings", (1, 2, 3, 4, 5), key="review_ratings")
        sentiments = st.multiselect("Sentiment", filter_options["sentiments"], key="review_sentiments")
        topic = st.selectbox("Topic", [None, *filter_options["topics"]], format_func=lambda value: "All topics" if value is None else value)
        pain_point_id = st.selectbox("Pain point", [None, *pain_options], format_func=lambda value: "All pain points" if value is None else pain_options[value])
        from_col, to_col = st.columns(2)
        with from_col:
            date_from = st.date_input("From", value=None, format="YYYY-MM-DD")
        with to_col:
            date_to = st.date_input("To", value=None, format="YYYY-MM-DD")
        st.form_submit_button("Apply filters", icon=":material/filter_alt:")

    if date_from and date_to and date_from > date_to:
        st.error("The From date must be before the To date.")
        st.stop()
    with session_scope() as session:
        rows = ReviewRepository(session).search(
            niche_id=niche_id,
            book_id=book_id,
            ratings=ratings,
            query=query,
            date_from=date_from if isinstance(date_from, date) else None,
            date_to=date_to if isinstance(date_to, date) else None,
            sentiments=sentiments,
            topic=topic,
            pain_point_id=pain_point_id,
        )
    st.metric("Matching reviews", len(rows))
    if not rows:
        st.info("No reviews match the current filters.")
        st.stop()

    frame = pd.DataFrame([
        {
            "ID": row["id"],
            "Book": row["book"],
            "Rating": row["rating"],
            "Title": row["title"],
            "Date": row["review_date"],
            "Review": row["body"],
            "Source": row["source"],
            "Sentiment": row["sentiment"],
            "Topics": ", ".join(row["topics"]),
        }
        for row in rows
    ])
    st.dataframe(
        frame,
        hide_index=True,
        key="review_table",
        column_config={
            "ID": st.column_config.NumberColumn(format="%d"),
            "Rating": st.column_config.NumberColumn(format="%d", min_value=1, max_value=5),
            "Date": st.column_config.DateColumn(format="MMM DD, YYYY"),
            "Review": st.column_config.TextColumn(width="large"),
        },
    )
    by_review_id = {row["id"]: row for row in rows}
    selected_review_id = st.selectbox(
        "Inspect a review",
        list(by_review_id),
        format_func=lambda value: f"#{value} — {by_review_id[value]['book']}",
        key="selected_review",
    )
    selected = by_review_id[selected_review_id]
    with st.container(border=True):
        st.write(f"**{selected['title'] or 'Untitled review'}** · {selected['rating'] or 'Unrated'} stars")
        st.caption(
            f"Source: {selected['source']} · Source review ID: "
            f"{selected['source_review_identifier'] or 'not supplied'} · "
            f"Verified purchase: {selected['verified_purchase'] if selected['verified_purchase'] is not None else 'not supplied'}"
        )
        st.text_area("Original text", selected["body"], disabled=True, height=120)
        st.text_area("Normalized text", selected["normalized_body"], disabled=True, height=120)
        if selected["sentiment"]:
            st.caption(f"Extracted sentiment: {selected['sentiment']} · Topics: {', '.join(selected['topics']) or 'none'}")
elif view == "Pain points":
    render_pain_points(niche_id)
elif view == "Praise":
    render_praise(niche_id)
else:
    render_analysis_history(niche_id)
