# banknifty_daily_raw
 The dataset contains 907 observations a/nd 5 columns
 no missing values
 no outliers
 date range is from 02-01-2023 to 31-08-2026
 date is currently stored as object                                                                  -----to be fixed  --DONE
 no invalid dates
 ohlc logically validated
 chronological order not followed- observations are stored as one date for each year                 -----to be fixed   --DONE


# constituent_change_events
4 observations and 6 columns, no missing values
effective_date is currntly object type                                                               -----to be         --DONE
source fact checked
constituent change has taken place on 30/09/2024 and 31/12/2025
Canara bank, union bank and yes bank have been iincluded which are still in the constituent compostion

# constituent_regime_members
38 observations and 3 columns
no. of banks- 12 in each R1,R2 and 14 in R3
start_snapshot_date is cuurently type object                                                         -----to be fixed   --DONE
consituent members inclusion validated
chnage const_reg_mem['start_snapshot_date'] to 02/09/2024 for R2 and 01/12/2025 for R3               -----to be fixed   --DONE

# constituent_regimes
contains 3 observations and 4 columns
start_snapshot_date	and end_snapshot_date are object data types                                     -------to be fixed      --DONE
validated constituents count in constituent_regime_members against constituent regimes dataset
invalid transition of regimes: R1 end : 29/09/2024 R2 end: 30/12/2025                               -------to be fixed     --DONE
trading day count mismatch between bank_nifty and constituents                                      -------to be fixed  --DONE


# constituent_stocks_raw
13620 observations and 7 columns
date is an object type                                                                              -------to be fixed        --DONE
data collected for all constituents for the entire rane irrespective of the regime membership
caught a bigger issue - KOTAKBANK AND HDFCBANK prices are incorrect at most places                  ------utmost priority        --DONE

# constituent_weights_raw
546 obsercations and 10 columns
date is objecttype                                                                                  -------to be fixed         --DONE
no missing record
no month's weightage is less than 99.98 and greater than 100.03 percent
no missing or extra month
weightage percentage range validated

# daily_weights_reconstruction

10494 observations and 4 columns
 date type object                                                                                   -------to be fixed        --DONE
jan 2023 entire month not calculated 09/2024 n 12/2025                                              -------to be fixed  --DONE
01-08-2025 hdfc weightage huge jump- weightage calculation formula needs rechecking                 -------to be fixed    DPNE


# earnings_raw
240 observations 10 columns
date,period_end,eps_actual,eps_forecast,revenue_actual,
revenue_forecast,eps_surprise,revenue_surprise,reaction all object type                             -------to be fixed   --DONE


# weight_reconstruction_validation
41 observations 11 columns
late_anchor, earlier_ anchor object type                                                            -------to be fixed   -DONE
two months records missing - 09-2024 and 12-2025                                                    -------to be fixed            --DONE