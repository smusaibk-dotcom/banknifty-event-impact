# 1. Bank_Nifty_Daily_Raw
This dataset contains the daily market data for the Nifty Bank index.
## Grain
one Bank Nifty trading day
## Primary Key
`date`- one date = one Bank Nifty observation
##  Attributes
date: trading session, open: opening price, high: highest price of session, close: closing price, low: lowest price of session
## Role in the Project
Provides the daily Bank Nifty index observations used to construct the movement target and evaluate constituent earnings-event impact.
## Relationship
at taabular level direct relationships are primarily temporal
## Data lineage
This is a source market-data table. It is not derived from the other project datasets. It serves as an input to target construction, event-impact analysis, and evaluation.
## Temporal Aspect
 this is a time dependent entity, each observation corresponds to a specific Bank Nifty trading session.

# 2. constituent_change_events
this dataset contains the information about changes in banknifty constituents
## Grain
One row represents one constituent membership change event.
## Primary Key
effective_date + symbol + event_type
## Attributes
effective_date: effective date of change, event_type: whether included or excluded ,symbol: ticker of constituent, previous_status: whether active or inactive in past,new_status: whether active or inactive now ,source: source of the information
## Relationship
contains exact dates for constructing regimes. Provides the membership-change events used to define/derive the constituent regimes.
# Data lineage
this is a reference data table, non derived. used to construct regimes
## temporal aspect
each effective date corresponds to the beginning of a new regime

# 3. constituent_regimes
Defines the historical constituent composition regimes used by the project
## Grain
one row represents one regime
## Primary key
regime_id
## Attributes
regime_id: represent different regimes,start_snapshot_date: start of the regime, end_snapshot_date: end of regime,constituent_count: no. of constituents during the regime
## Relationship
defines the time periods of the historical regimes and is related to constituent_regime_members, which identifies the constituents belonging to each regime
## Data lineage
this is a derived dataset from the constituent changes event
## temporal aspect
each regime has a duration



# 4. constituent_regime_members
defines the constituents during each regime
## Grain
one row represents one constituent during a particular regime
## Primary key
regime_id + symbol
## Foreign key
regime_id
## Attributes
regime_id: identifies a regime, start_snapshot_date: date of regime start ,symbol: ticker of constituent
## Relationship
defines the membership of a constituent in each regime and is related to constituent regimes which identifies the time period of each regime
## Data lineage
derived dataset from constituent_regimes and constituent change events
## temporal aspect
each member is associated with a regime which changes over the time


# 5. constituents_stocks_raw
defines the daily OHLC of the cosntituent
## Grain
one row represents one session of a constituent
## Primary key
date + symbol
## Attributes
date, symbol: ticker of constituent, open, high, low, close,volume: no. of shares traded on the day
## Relationship
The stock prices are an input used in reconstructing daily weights. And the stock data also provides the constituent returns used alongside the weights in the Bank Nifty analysis.
## Data lineage
this is a source market data, non derived
## temporal aspect
each observation corresponds to a specific constituent on a specific trading session


# 6. constituents_weights_raw
defines weightage of each constituent as rleased by NSE at month end
## Grain
one row represents weight of a constituent at month end
## Primary key
date + symbol
## Attributes
date: date of the release, symbol: ticker, security_name: constituent name, industry: industry classification, close_price: price atmonth end, index_mcap_rs_crores: market cap of the constituent, weightage_pct: official constituent weight in the index, source_month: month for which the weights were released,source_file: data source,weight_observation_type: period of observation for weights
## Relationship
The official monthly weight acts as an anchor/baseline for reconstructing daily constituent weights.
# Data lineage
this is a source data, non derived
## temporal aspect
eEach observation represents an official constituent-weight snapshot for a specific monthly observation date

# 7. daily_weights_reconstruction
defines weight of each constituent after the closing of a particular trading day
## Grain
one row represents weight of a constituent after the tradig session
## Primary key
date + symbol
## Attributes
date: trading session date, symbol: ticker, weight: weightage of a constituent, weight_source: whether calculated or source weight
## Relationship
this table will be required to calculate the impact of the constituent in the movement of banknifty
# Data lineage
this is a dervied dataset by using constituent_stock_raw, constituent_weights_raw
## temporal aspect
each observation represents a weightage at a particular day


# 8. weight_reconstruction_validation
defines the evaluation of the reconstructed weights
## Grain
One row represents the validation of one reconstruction interval at an anchor date
## Primary key
regime_id + later_anchor
## Attributes
regime_id: regime, later_anchor: base month, earlier_anchor: evaluation month, constituent_count: number of constituents in that month, mae: mean abs error between the official weights and the calculated weights ,rmse: root mean square abs error between the official weights and the calculated weights, max_abs_error: maximum absolute error between the official weights and the calculated weights, correlation; correlation between calculated and officila weights,reconstructed_weight_sum: summation of all calculated constituent weights at the earlier_anchor ,official_weight_sum: summation of official weightage of the constituents at the earlier anchor, status: validated or not
## Relationship
this dataset is used to validate the calculation strategy of the daily_weights_reconstruction against official observations in
constituent_weights_raw
## Data lineage
this is a derived dataset by taking weights of daily_weight_reconstruction and constituent_weights_raw
## temporal aspect
Validation is performed at historical monthly anchor points across
reconstruction intervals.


# 9. earnings_raw
defines the earnings data of each constituent
## Grain
One row represents one constituent's quarterly earnings announcement for a specific reporting period
## Primary key
symbol + date + period_end
## Attributes
symbol: ticker,date: date of announcemnt,period_end: end of reported financial period, eps_actual : reported eps ,eps_forecast: predicted eps, revenue_actual: reported revenue, revenue_forecast ;predicted revenue, eps_surprise: eps surprise percentage ,revenue_surprise: percentage surprise revenue , reaction: recorded market reaction
## Relationship
The earnings event identifies what happened and when. Market datasets provide the subsequent constituent and Bank Nifty response
## Data lineage
this is a source data
## Temporal aspect
time dependent event dataset. The announcement date determines the event timing and is required to align the earnings event with the subsequent trading session