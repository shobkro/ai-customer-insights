# DAX measures

> These measures are already in the ready-made project (`AI Customer Insights.pbip`),
> in the `_Measures` table, grouped into display folders. This page is the reference
> if you build the model by hand.

Create a blank table called `_Measures` (Home → Enter data → OK) and add these measures to it.
Format percentages as `%` and money as currency (BRL) in the Measure tools ribbon.

## Core sales

```DAX
Delivered Orders =
CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[order_status] = "delivered" )

Revenue =
CALCULATE ( SUM ( fact_orders[order_value] ), fact_orders[order_status] = "delivered" )

Avg Order Value =
DIVIDE ( [Revenue], [Delivered Orders] )

-- dim_customer is on the "one" side, so the order filter must be pushed back to it
-- with CROSSFILTER; without it every customer is counted, delivered or not
Customers =
CALCULATE (
    DISTINCTCOUNT ( dim_customer[customer_unique_id] ),
    fact_orders[order_status] = "delivered",
    CROSSFILTER ( fact_orders[customer_id], dim_customer[customer_id], BOTH )
)
```

## Time intelligence (needs dim_date marked as a date table)

```DAX
Revenue PM =
CALCULATE ( [Revenue], DATEADD ( dim_date[Date], -1, MONTH ) )

Revenue MoM % =
DIVIDE ( [Revenue] - [Revenue PM], [Revenue PM] )

Revenue YTD =
TOTALYTD ( [Revenue], dim_date[Date] )

-- Average of the last 3 *monthly* totals. (AVERAGEX over DATESINPERIOD alone would
-- average daily revenue, roughly 30x smaller than the monthly Revenue line.)
Revenue 3M Rolling Avg =
VAR LastDate = MAX ( dim_date[Date] )
VAR Months =
    CALCULATETABLE (
        VALUES ( dim_date[year_month] ),
        DATESINPERIOD ( dim_date[Date], LastDate, -3, MONTH )
    )
RETURN
    AVERAGEX ( Months, CALCULATE ( [Revenue] ) )
```

## Delivery & satisfaction

```DAX
Late Orders =
CALCULATE ( COUNTROWS ( fact_orders ), fact_orders[is_late] = 1 )

Late Delivery % =
DIVIDE (
    [Late Orders],
    CALCULATE ( COUNTROWS ( fact_orders ), NOT ISBLANK ( fact_orders[is_late] ) )
)

Avg Delivery Days =
CALCULATE ( AVERAGE ( fact_orders[delivery_days] ), fact_orders[order_status] = "delivered" )

Avg Review Score =
AVERAGE ( fact_reviews[review_score] )

% 1-2 Star Reviews =
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_reviews ), fact_reviews[review_score] <= 2 ),
    COUNTROWS ( fact_reviews )
)

Avg Score On Time =
CALCULATE ( [Avg Review Score], fact_orders[is_late] = 0 )

Avg Score Late =
CALCULATE ( [Avg Review Score], fact_orders[is_late] = 1 )

Score Gap Late vs On Time =
[Avg Score On Time] - [Avg Score Late]

Reviews =
COUNTROWS ( fact_reviews )
```

## AI review labels

```DAX
Labelled Reviews =
COUNTROWS ( review_ai_labels )

Negative Reviews (AI) =
CALCULATE ( COUNTROWS ( review_ai_labels ), review_ai_labels[sentiment] = "negative" )

Negative Share (AI) =
DIVIDE ( [Negative Reviews (AI)], [Labelled Reviews] )

High Urgency Reviews =
CALCULATE ( COUNTROWS ( review_ai_labels ), review_ai_labels[urgency] = "high" )

Topic Share of Complaints =
DIVIDE (
    [Negative Reviews (AI)],
    CALCULATE ( [Negative Reviews (AI)], ALL ( review_ai_labels[topic] ) )
)
```

## Dynamic title (nice touch for interviews)

```DAX
Overview Title =
"Revenue " & FORMAT ( [Revenue], "R$ #,0" ) & " · Late deliveries "
    & FORMAT ( [Late Delivery %], "0.0%" )
```
