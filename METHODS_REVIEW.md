# Methods review of Borenstein, Bushnell and Wolak (2002)

- **Paper:** Severin Borenstein, James B. Bushnell and Frank A. Wolak, "Measuring Market Inefficiencies in California's
  Restructured Wholesale Electricity Market," *American Economic Review* 92(5), December 2002, pp. 1376–1405.
- **Statistical focus:** the summer 2000 market power rents of $4,448 million (standard error $430 million) and the
  decomposition of the $6.94 billion rise in spending from summer 1999 to summer 2000 into 21% production cost, 20%
  competitive rents and 59% market power.
- **Review standard:** current AEA Data and Code Availability Policy, and standard reporting of estimates, uncertainty,
  sample construction and sensitivity to modeling assumptions for simulation-based counterfactuals.
- **What was read:** the full text of the working-paper version, CSEM WP-102 (University of California Energy
  Institute, June 2002), from the Haas School of Business website, including Tables 1–3 and Appendices A and B. The
  published AER version was not read; its abstract reports the same headline numbers. Appendix C and the figures were
  read only as described in the text. The Harvey and Hogan critiques were read only through the summary in Rajaraman
  and Alvarado, "(Dis)Proving Market Power" (2002, revised 2003).

## Methods summary

The paper builds an hourly counterfactual price for the California ISO control area from June 1998 to October 2000
(29 months, 22,681 hours mentioned in the text). For each hour it subtracts observed must-take output (nuclear, wind,
solar, qualifying facilities), observed hydro and geothermal output, and observed net imports adjusted by an import
supply curve from scheduling coordinators' adjustment bids, from metered demand plus upward regulation reserve. The
remainder must be met by the in-state fossil fleet, whose units are ordered by marginal cost built from heat rates
(California Energy Commission and Southern California Gas data), daily gas prices at two hubs plus distribution
charges, variable O&M and, in the South Coast air district, NOx permit prices. Forced outages are drawn 100 times per
hour using NERC 1993–1997 class rates. The expected marginal cost of the last needed unit is the competitive price, and
it is compared with the Power Exchange's unconstrained day-ahead price. Payments above competitive levels are summed
over hours and expressed as a share of total payments. A separate exercise divides summer payments into production
cost, competitive rents, market power rents and two inefficiency components.

## Research design

An accounting counterfactual (structural simulation of perfect competition) compared with observed prices. It is
descriptive of conduct in aggregate and does not identify which firms caused any gap, which the authors state.

## Sampling strategy

The full population of hours in the study window and all fossil units in the control area that were not under
must-take contracts. No sampling in the statistical sense. The window begins near the market's opening (April 1998)
and ends before the PX closed.

## Sample size

92 fossil units in the cost curve (footnote 32); hourly data for 29 months; 22,681 hours referred to in the export
discussion. The number of hours per summer is not tabulated.

## Inclusion and exclusion criteria

Fossil units not under must-take agreements are included; must-take, hydro and geothermal output are taken as observed.
June 1998 is reported but described as uninformative. Negative markups are retained in the main results. The criteria
for classifying units as must-take are described by category rather than listed unit by unit.

## Independent and dependent variables

The outcome is the hourly gap between the PX price and the simulated competitive price, weighted by metered generation
less must-take output. Inputs are metered demand, regulation requirements, observed hydro, must-take and imports, unit
heat rates, fuel and permit prices, O&M and outage rates. There are no regressors in the causal sense; Figure 3
relates the hourly Lerner index to residual fossil demand by kernel regression.

## Statistical methods

Monte Carlo expectation over forced outages (100 draws per hour); kernel regressions of marginal cost and the Lerner
index on residual demand; a heteroskedasticity- and autocorrelation-consistent standard error for summed payments above
cost, built from residuals of a reduced-form regression of the hourly markup on calendar dummies, forecast load and
reliability must-run requirements, summed by day, with a Bartlett kernel and 10 lags (Appendix B).

## Reported effect sizes

Monthly MP(S) from −51% (June 1998) to 63% (June 2000); 33% over all hours ($5.55 billion); summer market power rents
of $425M, $382M and $4,448M for 1998 to 2000; the 21/20/59 decomposition; import inefficiency rising from 2% to 8% of
production cost.

## Confidence intervals

Not reported as intervals. Standard errors are given for summed rents (whole sample and each summer), from which
intervals can be formed. No uncertainty is reported for the decomposition shares or for MP(S) itself.

## P-values, if applicable

None reported. The off-peak MP values of 1.9% and 1.8% are described as not significantly different from zero without
a test statistic.

## Missing data treatment

Not discussed. Data are described as complete hourly settlement records. How missing prices, outages in metering or
units without heat rate data were handled is not stated beyond the use of similar units for 27 start-up formulas.

## Stated limitations

The benchmark ignores unit-commitment costs and constraints, transmission congestion and local reliability, and
reliability must-run dispatch; the measure captures all inefficiencies, not only market power; hydro is assumed to be
scheduled efficiently; import bids are assumed to be at cost; rated capacities are treated as binding; demand is
treated as perfectly inelastic. The authors argue most of these bias the estimate downward.

## Statistics extraction table

| Statistic | Value and unit | Source location | What it measures | What it does not establish |
|---|---|---|---|---|
| Wholesale spending, summer 1999 and 2000 | $2.04B and $8.98B | Abstract; Table 3 | PX price times metered generation less must-take, June–October | Who received the payments or what share was refunded |
| Decomposition of the increase | 21% cost, 20% competitive rents, 59% market power | Abstract | Shares of the change attributable to each component | Uncertainty of the shares; no SE given |
| Market power rents by summer | $425M (46), $382M (41), $4,448M (430) | Appendix B; Table 3 | Sum of (PX − competitive price) × quantity | Which firms exercised market power, or whether it was unilateral or collusive |
| MP(S), whole sample | 33%, $5.55B (SE $1.19B) | Section V | Share of payments above competitive cost | Behavior outside the energy market (ancillary services, RMR) |
| Off-peak MP(S) | 1.9% and 1.8% | Section V | Markup in December–April periods | A formal test; also that costs are right in peak hours |
| Monthly PX price and marginal cost | e.g. Aug 2000 $166.24 vs $76.19 | Table 2 | Monthly means of hourly series | Hour-level distribution |
| Median import reduction and elasticity | 2.4%; 0.63 | Section V | Import response between actual and competitive prices | That out-of-state suppliers priced at cost |
| Instate and import inefficiency, summer 2000 | $126M and $221M | Table 3 | Extra production cost from misallocated output | Separation of import inefficiency from out-of-state rents |
| Start-up costs | $39M; 0.91% vs 0.37% of production cost | Section IV.E | Size of omitted non-convex costs | Their effect on hourly prices through commitment |
| Residual fossil demand, late summer | 6,639, 5,690 and 10,007 MW | Section V | Shift in demand facing in-state fossil units | Causes of the import decline |

## Interpretation notes

- The 59% share is a share of a change, and competitive rents rose too, so the paper does not claim market power
  caused the crisis alone; it shows higher costs and lower imports multiplied the dollar value of similar Lerner indices.
- The standard errors cover only uncertainty from realized forced outages in the PX price. They do not cover
  uncertainty in heat rates, fuel prices, outage rates or the import curve, which a reader would expect to dominate.
- Retaining negative markups is conservative for the total but makes monthly values in spring partly a measure of
  benchmark error, as the authors discuss for June 1998.
- The paper's Lerner index by residual demand is consistent with unilateral market power and also with scarcity rents
  that a static benchmark omits; the off-peak check is the main evidence for the first reading.
- The modern rerun in this repository follows the same accounting with public data. It is not a reproduction of the
  paper's estimates, and its California results cover different years and a much changed market.

## Unanswered questions

- How sensitive are the summer 2000 rents to the heat rate source and to unit-specific rather than class-average
  outage rates?
- What standard errors would the decomposition shares carry if cost-input uncertainty were included?
- How much of the import inefficiency was rents to out-of-state sellers rather than production loss?
- Were results sensitive to using the PX price rather than the ISO real-time price in the hours where they diverged?

## Items requiring expert verification

- Whether the AER version changed any table values relative to the June 2002 working paper read here.
- The classification of specific units as must-take, and the treatment of the Mohave plant, against ISO records.
- Whether NERC 1993–1997 class outage rates were representative of the divested California fleet in 2000.
- The content of the Harvey and Hogan papers, read here only through a secondary summary, and of the authors' replies.
