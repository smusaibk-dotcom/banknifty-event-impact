# Objective:
Quarterly earnings announcements of individual Nifty Bank constituents can cause substantial movements in the affected stock. Because that stock contributes to the index according to its weight, the event may transmit to Bank Nifty. Other constituents may simultaneously amplify or offset that impact.
We want to Verify whether our claim is right or wrong.

# Problem Statement:
Given a constituent's quarterly earnings outcome, should we expect an extra movement in Banknifty over its normal move during the subsequent trading session?

# Study Period:
January 2023 – August 2026

# Events:
Primary scope: quarterly earnings announcements of Nifty Bank constituents.

# Inputs:
1. Historical Index Weights
2. EPS data of Components
3. Bank Nifty Stock Data
4. Component Banking Stocks Data


If our Claim proved to be True then we will try to Quantify this Shock in another project which will be the continuation of this one where
our **Targets** would be:

Regression: 

$$ Y_r = \text{Bank Nifty excess move during the defined post-event window} $$

Classification:

$$ Y_c = \begin{cases} 1 & \text{Bank Nifty rises}\\ 0 & \text{Bank Nifty falls} \end{cases} $$


	​
