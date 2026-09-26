# Objective:
Quarterly earnings announcements of individual Nifty Bank constituents can cause substantial movements in the affected stock. Because that stock contributes to the index according to its weight, the event may transmit to Bank Nifty. Other constituents may simultaneously amplify or offset that impact.
We want to quantify and predict this transmission.

# Problem Statement:
Given a constituent's quarterly earnings outcome, what extra movement apart from daily average should we expect in Bank Nifty during the subsequent trading session?

# Study Period:
January 2023 – August 2026

# Events:
Primary scope: quarterly earnings announcements of Nifty Bank constituents.

# Inputs:
1. Historical Index Weights
2. EPS data of Components
3. Bank Nifty Index Data
4. Component Banking Stocks Data
5. Compnents ticker data

# Targets:

## Regression: 

$$ Y_r​=R_{BN,post−event}​−E[R_{BN,normal}​] $$

## Classification:

$$ Y_c = \begin{cases} 1 & \text{Bank Nifty rises}\\ 0 & \text{Bank Nifty falls} \end{cases} $$

# Baseline:

$$ \hat{R}_{BN} = \sum_{i} w_i R_i $$
