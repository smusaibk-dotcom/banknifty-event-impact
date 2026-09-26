# BANKNIFTY
- Birds ye view: theres a clear broad uptrend with approx 35% positive gain during the observation range , however trajectory isnot smooth, both 22 day SMA AND EMA second that with EMA resopnding to price changes faster than SMA.

Daily return analysis: Histogram is concentrated around 0% and the mean and median of the daily return is +0.03 & +0.04 meaning most trading days irectional return is close to 0 however the median absolute close to close movement is rought half a percent(~0.48%). largest move was downside on 04-06-2024 -the election result day. distributon concentrated around 0 while evidence of less frquent larger movements around tails

Opening gaps: median absolute gap is only 0.253% so on a typical day, Banknifty opens approx 0.25% away from the previous day's close, irrespective of direction. More Gap up opens than gap down (~57.16% more), it never opens flat

Intraday movement :-
- On normal trading days, Banknifty's Directional intraday returns are centered around zero, with a median movement of approx -0.02%. About 95% of normal-day intraday movements are within approx ±1.53% in absolute magnitude, and 99% are within approx ±2.16%. The distribution remains fat-tailed, with occasional normal-period extremes reaching around ±3%.
- 4 JUNE 2024 is excluded as a rare event.
- when comparing with overnight moves. Overnight distribution has a much tighter central box but many more extreme upper-tail observations, whereas intraday movement has the larger central distribution
- on a normal day banknifty moves about 1% btween low and high
- On a normal day, Bank,ifty moves about 0.43% upward and 0.47% downward from its opening. Downside move is slightly larger than upside.
- Whether Banknifty finishes the day positive or negative, its total intraday travel is remarkably similar. The direction of the close does not materially determine the day's total range.


Volatility :-
- During normal conditions, daily volatility is around 0.8–0.9%, but it can expand to 1.4%+ during high-volatility regimes and reach ~2.5% on a 22-day rolling basis.The volatility has short term memory fading away quickly as the days pass.


Calendar/time patterns — Ahe first half of the year, particularly April and June, shows stronger median daily returns, while July–August show weaker/negative median returns. But with only ~3.5 years of data, there is insufficient historical repetition to establish a persistent seasonal effect


-----------------------------------------------------------------

# Constituents
- Across the 15 Banknifty constituents, there is substantial variation in their normal movement intensity.
- BANDHANBNK, UNIONBANK and YESBANK are among the highest-volatility constituents, with daily volatility around 2.2–2.3%.
- ICICIBANK, HDFCBANK and KOTAKBANK are among the lowest, around 1.16–1.37%.
- Median absolute daily movement ranges from 0.60% (ICICIBANK) to 1.24% (UNIONBANK).
- Intraday ranges show a similar cross-constituent difference.
- Mean and median returns are generally close to zero, indicating that the major distinction between constituents is how much they move, rather than a persistent directional bias


--------------------------------------------------------
# Stocks-Earnings Level Analysis
- Earnings events produce a clear but constituent-specific increase in stock movement intensity, concentrated mainly at T0 and T+1. Most constituents show materially higher median absolute returns than their own normal baseline on T0/T+1, with particularly large shocks in KOTAKBANK, IDFCFIRSTB, ICICIBANK, AXISBANK and PNB. By T+2 the effect becomes mixed, and by T+3 it generally weakens or reverses. The effect is therefore primarily a short-lived volatility shock rather than a uniform directional effect, and its magnitude varies substantially across constituents

# Index Decomposition 
- Earnings events were associated with higher Banknifty movement intensity: median absolute Open-to-Close movement increased from 0.404% on normal days to 0.466% on T0 and 0.473% on T+1. Combined event days showed a 12.1% jump in median movement, while mean returns remained close to zero, suggesting increased volatility rather than a consistent directional effect
- Using all active constituents and their historical weights, the reconstructed index return had a 0.9925 correlation with actual Banknifty returns across 902 trading days. Mean actual return was +0.0360%, v/s +0.0512% reconstructed, with a median residual of only −0.0069 percentage points and median absolute residual of 0.0144
- Ky takeaway is that Banknifty normally behaves very much like the weighted sum of its constituent banks. Earnings announcements make the index move more, while simultaneously creating a larger gap between the simple weighted reconstruction and the actual index movement
- Actual stock movement is more closely related to Banknifty movement than raw earnings surprise. Strongest relationships were between weighted constituent return and Banknifty return:
T0 Spearman = 0.403 and T+1 = 0.417. In contrast, EPS surprise had only −0.058 (T0) and +0.029 (T+1) correlation with Banknifty return. This means raw surprise alone shows weak direct monotonic association with Banknifty movement.
- For majority-weight bank events, median Banknifty absolute movement was 0.554% on T0 and 0.346% on T+1, compared with 0.607% and 0.581% for lower-weight events meaning a bank's weight determines its potential influence, but the size of its actual stock reaction determines how much of that potential is realized.

# Daignostic EDA Wrap-Up:
Until this stage, our objective was to determine whether a relationship exists between earnings events at Banknifty constituent stocks and subsequent Banknifty movement.
And we established that earnings events are associated with increased movement intensity in the Banknifty, and that constituent-level movements, when considered alongside their index weights, closely explain the observed index movement. The effect is primarily a movement/volatility response rather than a consistent directional response.

we now move to the next question:
Given only the information available at the prediction time, can we predict whether Banknifty will move UP or DOWN, and can we predict the magnitude of that movement following an earnings event?.

*********************************************.



