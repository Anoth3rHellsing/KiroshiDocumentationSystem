# -*- coding: utf-8 -*-
import io
import re
import json
import logging
import pandas as pd
import altair as alt
import streamlit as st
from typing import Mapping
from datetime import datetime, timezone

from KiroshiApp.constants import ALTAIR_CHART_KWARGS
from KiroshiApp.services.data_manager import ensure_ai_learning_dataset, run_bug_detector
from KiroshiApp.services.pdf_generator import generate_ai_educate_report_pdf, generate_recurring_issue_pdf
from KiroshiApp.utils import (
    _cluster_case_titles, _summarize_text, _normalize_text_field, _coerce_int,
    _derive_analysis_label, _text_contains_bug
)

def render_responsive_altair_chart(chart: alt.Chart) -> None:
    st.altair_chart(chart, **ALTAIR_CHART_KWARGS)

def global_widget_key(base: str) -> str:
    # Duplicate for now or import from shared location if we had one
    return f"global_{base}"

def collect_ai_educate_report_data(
    dataset: Mapping[str, object] | None,
) -> dict[str, object]:
    if not dataset:
        return {}

    cases = dataset.get("cases", [])
    if not isinstance(cases, list) or not cases:
        return {}

    df = pd.DataFrame(cases)
    if df.empty:
        return {}

    df["timestamp"] = pd.to_datetime(df.get("timestamp"), unit="s", errors="coerce")
    df["saved_at_dt"] = pd.to_datetime(df.get("saved_at"), errors="coerce")
    df["event_time"] = df["timestamp"].where(df["timestamp"].notna(), df["saved_at_dt"])

    title_series = df.get("title")
    if isinstance(title_series, pd.Series):
        title_values = title_series.fillna("").astype(str).tolist()
    else:
        title_values = ["" for _ in range(len(df))]
    cluster_assignments, cluster_label_map = _cluster_case_titles(title_values)
    df["title_cluster_id"] = cluster_assignments
    cluster_labels: list[str] = []
    for assignment, title in zip(cluster_assignments, title_values):
        label = cluster_label_map.get(assignment)
        if not label:
            label = _summarize_text(title, width=80) if title else "Caso sin título"
        cluster_labels.append(label)
    df["title_cluster_label"] = cluster_labels
    cluster_label_series = pd.Series(cluster_labels, dtype="object")
    if cluster_label_series.empty:
        df["title_cluster_recurrence"] = 1
    else:
        cluster_counts = (
            cluster_label_series[cluster_label_series != ""].value_counts()
        )
        if cluster_counts.empty:
            df["title_cluster_recurrence"] = 1
        else:
            df["title_cluster_recurrence"] = (
                df["title_cluster_label"].map(cluster_counts).fillna(1).astype(int)
            )

    root_cause_series = df.get("root_cause", pd.Series(dtype="object"))
    root_cause_norm = root_cause_series.apply(_normalize_text_field)
    root_cause_labels: dict[str, str] = {}
    if isinstance(root_cause_series, pd.Series):
        for original, normalized in zip(root_cause_series.tolist(), root_cause_norm.tolist()):
            if normalized and normalized not in root_cause_labels and isinstance(original, str):
                root_cause_labels[normalized] = original
    root_cause_counts = root_cause_norm[root_cause_norm != ""].value_counts()

    existing_recurrence = df.get("recurrence_count")
    if isinstance(existing_recurrence, pd.Series):
        df["recurrence_count"] = existing_recurrence.apply(_coerce_int)
    else:
        df["recurrence_count"] = 0
    df["recurrence_count"] = df["recurrence_count"].fillna(0).astype(int)
    df["root_cause_norm"] = root_cause_norm
    df["root_cause_recurrence"] = df["root_cause_norm"].map(root_cause_counts).fillna(1).astype(int)
    df["recurrence_count"] = (
        df[["recurrence_count", "root_cause_recurrence", "title_cluster_recurrence"]]
        .max(axis=1)
        .astype(int)
    )

    scanner_series = df.get("scanner_model")
    if scanner_series is None:
        for alt_col in ("scanner", "scanner_type", "scanner_sn"):
            if alt_col in df.columns:
                scanner_series = df.get(alt_col)
                if scanner_series is not None:
                    break
    if scanner_series is None:
        scanner_series = pd.Series(["" for _ in range(len(df))])
    scanner_norm = scanner_series.apply(_normalize_text_field)
    df["scanner_norm"] = scanner_norm
    scanner_labels: dict[str, str] = {}
    for original, normalized in zip(scanner_series.tolist(), scanner_norm.tolist()):
        if normalized and normalized not in scanner_labels and isinstance(original, str):
            scanner_labels[normalized] = original

    analysis_context = {
        "root_cause_labels": root_cause_labels,
        "scanner_labels": scanner_labels,
    }
    df["analysis_label"] = df.apply(
        _derive_analysis_label, axis=1, args=(analysis_context,)
    )

    analysis_counts = df["analysis_label"].value_counts()
    df["analysis_recurrence"] = (
        df["analysis_label"].map(analysis_counts).fillna(1).astype(int)
    )
    df["recurrence_count"] = (
        df[[
            "recurrence_count",
            "analysis_recurrence",
            "title_cluster_recurrence",
        ]]
        .max(axis=1)
        .astype(int)
    )

    now = pd.Timestamp.utcnow().tz_localize(None)
    recent_cutoff = now - pd.Timedelta(days=30)
    df["event_time"] = pd.to_datetime(df["event_time"], errors="coerce")
    recent_cases = df[df["event_time"] >= recent_cutoff]

    def _build_counts(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["analysis_label", "count"])
        counts = (
            frame.groupby("analysis_label")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        return counts

    overall_counts = _build_counts(df)
    recent_counts = _build_counts(recent_cases)

    highlight_case: dict[str, object] | None = None
    highlight_label = None
    highlight_count = 0
    if not overall_counts.empty:
        row = overall_counts.iloc[0]
        highlight_label = str(row["analysis_label"])
        highlight_count = int(row["count"])
        candidate = (
            df[df["analysis_label"] == highlight_label]
            .sort_values("event_time", ascending=False)
            .head(1)
        )
        if not candidate.empty:
            highlight_case = candidate.iloc[0].to_dict()

    bug_mask = df.apply(
        lambda row: _text_contains_bug(
            row.get("root_cause"),
            row.get("solution"),
            row.get("description_excerpt"),
            row.get("title"),
        ),
        axis=1,
    )
    bug_cases = df[bug_mask]
    bug_solution_mask = df.apply(
        lambda row: _text_contains_bug(row.get("solution"), row.get("root_cause")),
        axis=1,
    )

    recent_mask = df["event_time"] >= recent_cutoff
    bug_mentions_recent = int((bug_mask & recent_mask).sum())
    bug_solution_recent = int((bug_solution_mask & recent_mask).sum())

    def _build_timeline(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["timestamp", "count"])
        timeline = (
            frame.dropna(subset=["event_time"])
            .set_index("event_time")
            .resample("D")
            .size()
            .rename("count")
            .reset_index()
        )
        return timeline

    timeline_recent = _build_timeline(recent_cases)
    timeline_all = _build_timeline(df)

    recurring_issue_types = overall_counts[overall_counts["count"] >= 2]

    root_cause_summary = (
        df[df["root_cause_norm"] != ""]
        .groupby("root_cause_norm")
        .agg(count=("root_cause_norm", "size"))
        .reset_index()
        .sort_values("count", ascending=False)
    )
    if not root_cause_summary.empty:
        root_cause_summary["root_cause"] = root_cause_summary["root_cause_norm"].map(
            root_cause_labels
        )
        root_cause_summary = root_cause_summary[["root_cause", "count"]]

    scanner_summary = (
        df[df["scanner_norm"] != ""]
        .assign(scanner_display=lambda frame: frame["scanner_norm"].map(scanner_labels))
        .groupby(["scanner_norm", "scanner_display"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    if not scanner_summary.empty:
        scanner_summary.rename(
            columns={"scanner_display": "scanner"}, inplace=True
        )
        scanner_summary = scanner_summary[["scanner", "count"]]
    else:
        scanner_summary = pd.DataFrame(columns=["scanner", "count"])

    view_totals = {
        "all_time": {
            "case_total": int(len(df)),
            "bug_solution_count": int(bug_solution_mask.sum()),
            "bug_mentions_count": int(bug_mask.sum()),
            "unique_labels": int(overall_counts["analysis_label"].nunique()) if not overall_counts.empty else 0,
        },
        "30d": {
            "case_total": int(len(recent_cases)),
            "bug_solution_count": bug_solution_recent,
            "bug_mentions_count": bug_mentions_recent,
            "unique_labels": int(recent_counts["analysis_label"].nunique()) if not recent_counts.empty else 0,
        },
    }

    insights = {
        "recent_counts": recent_counts,
        "overall_counts": overall_counts,
        "counts": {"30d": recent_counts, "all_time": overall_counts},
        "timeline": timeline_recent,
        "timeline_all": timeline_all,
        "bug_cases": bug_cases,
        "bug_mentions_count": int(bug_mask.sum()),
        "bug_solution_count": int(bug_solution_mask.sum()),
        "bug_mentions_recent": bug_mentions_recent,
        "bug_solution_recent": bug_solution_recent,
        "highlight_case": highlight_case,
        "highlight_label": highlight_label,
        "highlight_count": highlight_count,
        "recent_total": int(len(recent_cases)),
        "case_total": int(len(df)),
        "view_totals": view_totals,
        "recurring_issue_types": recurring_issue_types,
        "common_root_causes": root_cause_summary,
        "common_scanner_models": scanner_summary,
    }

    return insights

def render_report_panel() -> None:
    st.subheader("AI Educate Report")
    if not st.session_state.get("ai_educate_enabled"):
        st.info("Activa AI Educate desde Settings para generar reportes.")
        return
    dataset = ensure_ai_learning_dataset()
    if not dataset:
        st.info("Aún no hay suficientes casos guardados para generar estadísticas.")
        return
    cached_insights = st.session_state.get("ai_educate_report_cache")
    dataset_case_total = dataset.get("case_count") if isinstance(dataset, Mapping) else None
    if (
        isinstance(cached_insights, Mapping)
        and dataset_case_total is not None
        and cached_insights.get("case_total") == dataset_case_total
    ):
        insights = cached_insights
    else:
        insights = collect_ai_educate_report_data(dataset)
        if insights:
            st.session_state.ai_educate_report_cache = insights
    if not insights:
        st.info("Aún no hay suficientes casos guardados para generar estadísticas.")
        return

    view_order = ["30d", "all_time"]
    view_labels = {"30d": "Últimos 30 días", "all_time": "Todo el historial"}
    default_view = st.session_state.get("ai_report_view", "30d")
    if default_view not in view_order:
        default_view = "30d"
    selected_view = st.radio(
        "Rango de tiempo",
        options=view_order,
        index=view_order.index(default_view),
        format_func=lambda key: view_labels.get(key, key),
        horizontal=True,
        key=global_widget_key("ai_report_view"),
    )
    st.session_state.ai_report_view = selected_view

    view_totals = insights.get("view_totals", {})
    current_totals = view_totals.get(selected_view, {})

    cols = st.columns(4)
    cols[0].metric(
        f"Casos ({view_labels[selected_view]})",
        current_totals.get("case_total", 0),
    )
    cols[1].metric(
        "Tipos de caso únicos",
        current_totals.get("unique_labels", 0),
    )
    cols[2].metric(
        "Solucionados como bug",
        current_totals.get("bug_solution_count", 0),
    )
    cols[3].metric(
        "Menciones de 'bug'",
        current_totals.get("bug_mentions_count", 0),
    )

    if selected_view != "all_time":
        overall_totals = view_totals.get("all_time", {})
        st.caption(
            f"Historial completo: {overall_totals.get('case_total', 0)} casos · "
            f"{overall_totals.get('unique_labels', 0)} tipos únicos"
        )

    highlight_label = insights.get("highlight_label")
    if highlight_label:
        st.markdown(
            f"**Caso prioritario:** {highlight_label} "
            f"(detectado {insights.get('highlight_count', 0)} veces)."
        )
        highlight_case = insights.get("highlight_case") or {}
        solution_excerpt = highlight_case.get("solution_excerpt")
        if solution_excerpt:
            st.caption(f"Insight de solución: {solution_excerpt}")

    counts_map = insights.get("counts", {})
    selected_counts = counts_map.get(selected_view)
    if isinstance(selected_counts, pd.DataFrame) and not selected_counts.empty:
        st.markdown(
            f"### Casos más frecuentes ({view_labels[selected_view]})"
        )
        st.dataframe(
            selected_counts.rename(
                columns={"analysis_label": "Caso", "count": "Frecuencia"}
            ),
            width="stretch",
        )
        freq_chart = (
            alt.Chart(selected_counts)
            .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
            .encode(
                x=alt.X("count:Q", title="Casos"),
                y=alt.Y("analysis_label:N", sort="-x", title="Caso"),
                tooltip=[
                    alt.Tooltip("analysis_label:N", title="Caso"),
                    alt.Tooltip("count:Q", title="Frecuencia"),
                ],
                color=alt.value("#2563eb"),
            )
            .properties(height=min(360, 40 * len(selected_counts)))
        )
        render_responsive_altair_chart(freq_chart)

    timeline_map = {
        "30d": insights.get("timeline"),
        "all_time": insights.get("timeline_all"),
    }
    selected_timeline = timeline_map.get(selected_view)
    if isinstance(selected_timeline, pd.DataFrame) and not selected_timeline.empty:
        st.markdown(f"### Tendencia de casos ({view_labels[selected_view]})")
        timeline_chart = (
            alt.Chart(selected_timeline)
            .mark_line(point=True, color="#16a34a")
            .encode(
                x=alt.X("timestamp:T", title="Fecha"),
                y=alt.Y("count:Q", title="Casos"),
                tooltip=[
                    alt.Tooltip("timestamp:T", title="Fecha"),
                    alt.Tooltip("count:Q", title="Casos"),
                ],
            )
            .properties(height=260)
        )
        render_responsive_altair_chart(timeline_chart)

    recurring_df = insights.get("recurring_issue_types")
    if isinstance(recurring_df, pd.DataFrame) and not recurring_df.empty:
        st.markdown("### Patrones recurrentes")
        st.dataframe(
            recurring_df.rename(
                columns={"analysis_label": "Caso", "count": "Recurrencias"}
            ),
            width="stretch",
        )

    root_cause_df = insights.get("common_root_causes")
    if isinstance(root_cause_df, pd.DataFrame) and not root_cause_df.empty:
        st.markdown("### Causas raíz más comunes")
        st.dataframe(
            root_cause_df.rename(columns={"root_cause": "Causa", "count": "Casos"}),
            width="stretch",
        )

    scanner_df = insights.get("common_scanner_models")
    if isinstance(scanner_df, pd.DataFrame) and not scanner_df.empty:
        st.markdown("### Modelos de escáner reportados")
        st.dataframe(
            scanner_df.rename(columns={"scanner": "Modelo", "count": "Casos"}),
            width="stretch",
        )

    bug_report = st.session_state.get("ai_bug_report")
    bug_cases = insights.get("bug_cases")
    if isinstance(bug_cases, pd.DataFrame) and not bug_cases.empty:
        st.markdown("### Casos con mención de bug")
        st.dataframe(
            bug_cases[["case_id", "title", "saved_at"]]
            .rename(
                columns={
                    "case_id": "Case ID",
                    "title": "Título",
                    "saved_at": "Guardado",
                }
            )
            .head(15),
            width="stretch",
        )

    col_pdf, col_bug = st.columns([1, 1])
    with col_pdf:
        try:
            pdf_bytes = generate_ai_educate_report_pdf(insights, bug_report)
        except Exception as exc:
            st.error(f"No se pudo generar el PDF del reporte: {exc}")
            pdf_bytes = None
        if pdf_bytes:
            st.download_button(
                "Descargar reporte PDF",
                pdf_bytes,
                file_name="ai_educate_report.pdf",
                mime="application/pdf",
                key=global_widget_key("ai_educate_report_pdf"),
            )
    with col_bug:
        if st.button(
            "Bug Detector",
            help="Analiza todos los casos guardados para encontrar patrones de bug.",
            key=global_widget_key("ai_bug_detector"),
        ):
            bug_report = run_bug_detector(dataset)
            st.session_state.ai_bug_report = bug_report
            if bug_report:
                st.success("Bug Detector completó el análisis.")
            else:
                st.info("No se detectaron bugs ni patrones recurrentes en los casos analizados.")
    bug_report = st.session_state.get("ai_bug_report")
    if bug_report:
        st.markdown("### Resultados de Bug Detector")
        st.write(bug_report.get("summary"))
        recurring = bug_report.get("recurring_patterns") or []
        if recurring:
            recurring_df = pd.DataFrame(recurring)
            if not recurring_df.empty and {"pattern", "count"}.issubset(recurring_df.columns):
                display_df = recurring_df[["pattern", "count"]]
            else:
                display_df = recurring_df
            st.table(
                display_df.rename(
                    columns={"pattern": "Patrón", "count": "Recurrencias"}
                )
            )

            eligible_patterns = [
                entry
                for entry in recurring
                if isinstance(entry, Mapping)
                and int(entry.get("count") or 0) >= 2
                and entry.get("pattern")
            ]
            if eligible_patterns:
                st.markdown("#### Generar guía para patrones recurrentes")
                options = [
                    f"{str(entry.get('pattern'))} ({int(entry.get('count', 0))})"
                    for entry in eligible_patterns
                ]
                selected_label = st.selectbox(
                    "Selecciona un patrón",
                    options,
                    key=global_widget_key("recurring_pattern_select"),
                )
                selected_entry: Mapping[str, object] | None = None
                for entry, label in zip(eligible_patterns, options):
                    if label == selected_label:
                        selected_entry = entry
                        break
                if selected_entry:
                    try:
                        pattern_pdf = generate_recurring_issue_pdf(
                            selected_entry,
                            dataset=dataset,
                        )
                    except Exception as exc:
                        st.error(f"No se pudo generar la guía del patrón: {exc}")
                    else:
                        raw_name = str(selected_entry.get("pattern", "patron"))
                        slug = re.sub(r"[^A-Za-z0-9]+", "-", raw_name.lower()).strip("-")
                        file_name = f"recurring_{slug or 'patron'}.pdf"
                        st.download_button(
                            "Descargar guía PDF",
                            pattern_pdf,
                            file_name=file_name,
                            mime="application/pdf",
                            key=global_widget_key("recurring_pattern_pdf"),
                        )
