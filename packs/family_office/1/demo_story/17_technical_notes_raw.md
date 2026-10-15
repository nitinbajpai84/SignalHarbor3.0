Synthetic, illustrative: invented for demonstration

# Technical notes on the numbers (Arjun's working file)

Illustrative Lakeside Family Office (ILFO). Kept by Arjun Rao for himself and the Finance Officer. Rough. Not every measure is here. Where a line says "ask", I have not written it down yet.

## Cash cushion
- Source: Northgate Custody daily file, NGC_Statement_YYYYMMDD.csv, then my consolidation workbook.
- Columns: statement_date, account_ref, currency, closing_balance.
- Steps: take the month-end closing_balance for each account, convert USD at the rate I type from the portal, add approved inflows, subtract obligations and the reserve, repeat for six months, take the lowest.
- Rate date and source of the FX rate: not noted. Ask Tom.

## Known obligations
- Source: Capital_Call_Tracker.xlsx, tab Calls.
- Columns: fund_code, call_amount, currency, notice_date, status.
- Steps: filter status not Paid and not Superseded, put each row in the month of its notice_date, sum by currency, convert to SGD.
- Note: Sara says bucket by due_date, and I have never changed it.

## Unfunded commitments
- Source: Capital_Call_Tracker.xlsx, tab Commitments.
- Columns: commitment_amount, called_to_date, recalled_distributions.
- Formula: =commitment_amount - called_to_date + recalled_distributions
- Complete. The cell is sometimes overwritten by hand. The fee element (fee_amount_in_call on the Calls tab) is not part of this.

## Old valuations
- Source: Bluewater share, BW_NAV_Report_YYYYMM.xlsx.
- Columns: report_month_end, nav_local, valuation_date, valuation_basis.
- Steps: age = report_month_end minus valuation_date; value of rows with age over the limit divided by total value.
- Age is counted in quarters in my workbook, not days. Limit: ask Mei. This differs from the glossary, which talks about a valuation date older than a limit; I use the quarter the manager statement covers.

## Single-name exposure
- Source: Exposure_Workbook.xlsx, tab Holdings and look-through (Wei's).
- Columns: issuer_group, exposure_route, value_sgd.
- Steps: sum value_sgd by issuer_group over direct and look_through rows, divide by total included assets.
- Partial: issuer_group is set by hand. Ask Wei.

## Private share
- Source: the exposure workbook, columns asset_class and value_sgd.
- Formula: =SUMIF(asset_class,"PE and VC",value_sgd)/SUM(value_sgd)
- Complete. Private credit and real assets are not in this one.

## Alpha
- Source: Performance_Workbook.xlsx, tabs Public, Private, Benchmarks.
- Columns: fund_code, return_method, period_return, benchmark_id, benchmark_return, excess_return.
- Formula: =period_return - benchmark_return
- Index levels are pasted from a vendor download; the close date is not always kept (level_source_date). Private funds use the net IRR from the manager statement, the public fund the time-weighted return.
- Disagrees with the glossary: the glossary says the numbers come from the tracker. They come from this workbook.

## Notices to chase
- Source: calls mailbox and Capital_Call_Tracker.xlsx.
- Columns: status, notes, superseded_by.
- Steps: count rows where notes is not empty and status is not Paid. Whether a Superseded row counts: ask Sara.

## Pay inputs matched
- Source: Pay_Review_Workbook.xlsx, tab Review, and my performance workbook.
- Columns: employee_ref, performance_score, review_date.
- Steps: compare performance_score on each row with my figure for the same period; count matches over rows.
- The denominator is the rows in the Review tab, which is everyone HR lists, not only the investment team. Ask Lina.

## Personal data and who may see it (rough)
- Personal data: employee_name, role, salary_band, target_bonus, recommended_bonus, approved_by in the pay workbook. The narrative and counterparty columns in the custody transactions file may name family members; treat as personal until confirmed.
- Pay file: HR Lead and Head of Investments, I think. Finance should see totals only, but the folder is open to us at the moment.
