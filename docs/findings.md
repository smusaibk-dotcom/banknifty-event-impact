# Data Analysis — Findings & Conclusion

## Question

Are quarterly earnings announcements of Banknifty constituent stocks associated with increased Banknifty movement, and what constituent-level factors help explain that movement?

The analysis focuses on whether constituent-level earnings events are associated with changes in Banknifty movement intensity and whether constituent movement and index weights help explain the observed index response.

## Key Findings

### Earnings events increase movement intensity

Banknifty showed higher median absolute Open-to-Close movement on earnings-event days compared with normal days.
- Normal days: 0.404%
- T0: 0.466%
- T+1: 0.473%
- Combined event days: 0.453%
This corresponds to approximately `15.4% higher movement on T0 and 17.2% higher movement on T+1 relative to normal days`. Across combined event days, median movement was approximately 12.1% higher.
Mean returns remained close to zero, indicating that the primary effect observed was increased movement intensity rather than a consistent upward or downward direction.

### The effect is concentrated around the earnings event
At the constituent level, the increase in movement intensity was primarily concentrated around T0 and T+1 and generally declined in subsequent sessions. Further No obvious sign of pre-event reaction(T-1,T-2 etc) was found.
This suggests that the earnings-related movement shock is relatively short-lived rather than a persistent multi-day effect.

### Constituent reactions matter for index movement
Constituent-level movements showed a relationship with Banknifty movement, particularly when constituent returns were considered together with their index weights.
The weighted constituent return had a stronger relationship with Banknifty return than earnings surprise variables alone.

### Index reconstruction explains most of the observed movement

A weight-based reconstruction of Banknifty returns showed a `correlation of approximately 0.993` with the actual Banknifty returns over the available period.
This indicates that constituent returns and their weights explain most of the day-to-day index movement.
However, the residual between reconstructed and actual index returns became larger around earnings events, indicating that simple constituent-weight reconstruction does not completely capture the event-period behaviour.

### Weight alone does not determine the index response
Higher-weight constituents have greater potential influence on the index, but a high constituent weight does not automatically produce a larger Banknifty movement. The actual stock reaction is necessary for that potential influence to translate into an observable index effect.
Lower-weight constituents can also produce meaningful index effects when their individual earnings-related movement is sufficiently large.

## Final Conclusion

The analysis establishes that constituent earnings announcements are associated with increased Banknifty movement intensity, particularly on T0 and T+1. The effect is primarily visible in movement magnitude rather than consistent direction.

Constituent movement and index weight together provide a stronger explanation of Banknifty movement than earnings-surprise variables considered independently. The analysis also shows that the effect is concentrated around the immediate earnings-event window and generally weakens afterward.

Therefore, earnings events provide a meaningful event-based context for analysing Banknifty movement.

This completes the Data Analysis stage.

The project can now transition from:

**Descriptive / Diagnostic Analysis**

to:

**Predictive Data Science — T+1 Direction + Excess Movement Prediction**