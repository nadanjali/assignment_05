"""
payroll_report_app.py — the quarter at a glance, for someone who never opens a terminal.

Every Friday since September the office manager at Salt City Coffee has downloaded
a payroll export from the Assignment 04 app; before that she typed the same file
by hand. The owner now wants to know where the hours went this quarter, the
accountant wants pay by month and department, and the manager wants to see who
has been missing shifts. This page answers all three from the pile of exports.

Same shape as Assignment 04: the page *assembles* the pipeline — one call to
`build_history` does the cleaning — and then shows the reports, filtered by the
department and dates the user picks.

Run it:  Run and Debug -> "Streamlit Run: Current File"
Test it: pytest tests/test_pipeline.py -k app
"""
# --- The page ---------------------------------------------------------------------
#
# No scaffolding. Every function this page needs already exists in the payroll
# package, and every widget it needs you used in Assignments 03 and 04 — plus two
# new ones, st.date_input and st.bar_chart. README Step 8 has the exact widgets,
# keys and labels; the tests in tests/test_pipeline.py -k app check them.
#
# The shape, in words:
#
#   title and a sentence of instructions
#   roster   <- load_employees()                           (fixed; not uploaded)
#   uploads  <- st.file_uploader, key="exports", accept_multiple_files=True
#               (an empty list until files are chosen)
#   if there are uploads:
#       history <- build_history([load_export(u) for u in uploads], roster)
#       st.warning naming any employeeid with no department (not on the roster);
#           the reports below use only the rows that matched
#       st.selectbox, key="department": "All" plus each department
#       st.date_input, key="dates": a (start, end) range, defaulting to the first
#           and last pay_date — compare against pay_date.dt.date to filter
#       the selection as a subheader
#       four st.metric cards in st.columns(4): Weeks, Employees, Total hours,
#           Total gross pay — counts are .nunique(), totals are .sum()
#       st.bar_chart of pay_by_month(selected), with month as the x axis
#       st.dataframe of summarize_employees(selected)
#       st.dataframe of hours_grid(selected), then of missed_weeks(that grid)
#       st.download_button, key="download": pay_by_month(...).to_csv(index=False)
#
# What the page does NOT do: cleaning, grouping, pivoting. If you find yourself
# writing a groupby or a pivot_table here, that logic belongs in the package.

import streamlit as st
import pandas as pd

from payroll import (
    build_history,
    clean_employee_id,
    hours_grid,
    load_employees,
    load_export,
    missed_weeks,
    pay_by_month,
    summarize_employees,
)

st.title("Salt City Coffee — Quarterly Payroll Report")
st.write(
    "Upload the weekly payroll exports for the period you want to review — old "
    "spreadsheet weeks and new app weeks can be mixed. The roster is loaded "
    "automatically."
)

roster = load_employees()
uploads = st.file_uploader(
    "Upload weekly payroll exports (CSV)",
    type="csv",
    accept_multiple_files=True,
    key="exports",
)

if uploads:
    uploads_for_history = []
    for upload in uploads:
        upload.seek(0)
        uploads_for_history.append(load_export(upload))
    history = build_history(uploads_for_history, roster)

    raw_exports = []
    for upload in uploads:
        upload.seek(0)
        raw_exports.append(load_export(upload))
    raw_exports = pd.concat(raw_exports, ignore_index=True)
    raw_exports["employee_id"] = clean_employee_id(raw_exports["employeeid"])
    roster_ids = set(roster["employee_id"])
    unmatched = sorted(
        raw_exports.loc[~raw_exports["employee_id"].isin(roster_ids), "employeeid"]
        .str.strip()
        .str.upper()
        .drop_duplicates()
    )
    if unmatched:
        st.warning(f"Unmatched employee IDs were left out of the report: {', '.join(unmatched)}")

    matched = history[history["department"].notna()].copy()
    departments = ["All"] + sorted(matched["department"].dropna().unique().tolist())
    department = st.selectbox("Department", departments, key="department")

    if department != "All":
        matched = matched[matched["department"] == department]

    start = matched["pay_date"].min().date() if not matched.empty else pd.Timestamp("2026-01-01").date()
    end = matched["pay_date"].max().date() if not matched.empty else pd.Timestamp("2026-12-31").date()
    selected_range = st.date_input("Date range", (start, end), key="dates")
    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start, end = selected_range
    if hasattr(start, "date"):
        start = start.date()
    if hasattr(end, "date"):
        end = end.date()

    selected = matched[
        (matched["pay_date"].dt.date >= start) & (matched["pay_date"].dt.date <= end)
    ].copy()

    st.subheader(
        f"Selected: {department if department != 'All' else 'All departments'} — "
        f"{start.isoformat()} to {end.isoformat()}"
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Weeks", str(selected["week_ending"].nunique()))
    col2.metric("Employees", str(selected["employee_id"].nunique()))
    col3.metric("Total hours", f"{selected['hours_worked'].sum():,.2f}")
    col4.metric("Total gross pay", f"${selected['gross_pay'].sum():,.2f}")

    monthly = pay_by_month(selected)
    st.bar_chart(monthly, x="month")

    st.dataframe(summarize_employees(selected))
    grid = hours_grid(selected)
    st.dataframe(grid)
    st.dataframe(missed_weeks(grid))
    st.download_button(
        label="Download CSV",
        data=monthly.to_csv(index=False),
        file_name="payroll_report.csv",
        key="download",
    )


