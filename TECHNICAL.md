# Technical notes

This is the technical companion to the [README](README.md). Every table the scripts produce is in
[results/FINDINGS.md](results/FINDINGS.md).

## The original study

Severin Borenstein, James B. Bushnell and Frank A. Wolak, "Measuring Market Inefficiencies in California's
Restructured Wholesale Electricity Market," *American Economic Review* 92(5), 2002, pp. 1376–1405 (working paper CSEM
WP-102, June 2002, the version read here). For every hour from June 1998 to October 2000 the authors simulate the
price-taking marginal cost of California's in-state fossil fleet, with 100 Monte Carlo forced-outage draws per hour, and
compare it with the Power Exchange's unconstrained day-ahead price. Headline numbers, quoted from the paper: spending
rose from $2.04 billion (summer 1999) to $8.98 billion (summer 2000), of which 21% was production cost, 20% competitive
rents and 59% market power; market power rents were $425M (SE $46M), $382M ($41M) and $4,448M ($430M) in the summers
of 1998 to 2000; MP(S) was 33% over the whole sample ($5.55B, SE $1.19B) and 1.9% and 1.8% in the two December-to-April
periods.

## Headline results

| Market and period | Buyers paid | Market power rents (SE) | MP |
|---|---|---|---|
| CAISO, summer 2024, hourly | $2,892M | $156M ($68M) | 5.4% |
| CAISO, summer 2025, hourly | $2,504M | −$88M ($38M) | −3.5% |
| CAISO, summer 2022, on-peak index | $3,780M | $53M | 1.4% |
| ERCOT, summer 2022, hourly | $11,271M | $3,867M ($820M) | 34.3% |
| ERCOT, summer 2023, hourly | $17,285M | $13,011M ($2,500M) | 75.3% |

The CAISO 2021 to 2022 on-peak change (+$1,150M) splits 56% production cost, 70% competitive rents, −26% market power.
The ERCOT 2022 to 2023 change (+$6,014M) splits −35%, −17% and +152%. The on-peak index understates the CAISO level:
in the on-peak hours of summers 2024 and 2025 its MP is −14.4% and −42.5% against 10.1% and −5.7% with the hourly
system energy price (`ice_vs_dayahead_check.csv`). That 12-point drift in one year is as large as the 2021 to 2022
change, so the index series does not establish a fall in market power.

## Data

All files in `data/raw/` were downloaded on November 1, 2026 by `src/fetch_data.py`.

| File | Source |
|---|---|
| `eia930_CISO_hourly.csv.gz`, `eia930_ERCO_hourly.csv.gz` | EIA-930 balancing-authority files (`CISO.xlsx`, `ERCO.xlsx`), "Adjusted" demand, interchange and net generation by fuel, 2019–2025 |
| `caiso_dam_prices.csv.gz` | CAISO OASIS `PRC_LMP`, day-ahead, node `TH_SP15_GEN-APND`, energy component (MCE) and LMP, August 2023–December 2025 |
| `ice_onpeak_daily.csv` | EIA `ice_electric-<year>final.xlsx`, "SP15 EZ Gen DA LMP Peak" weighted average price by delivery day |
| `ercot_dam_hubavg.csv.gz` | ERCOT report 13060, Historical DAM Load Zone and Hub Prices, `HB_HUBAVG` |
| `fleet_generators.csv.gz` | PUDL v2026.10.0 `out_eia__yearly_generators`, existing gas, oil and coal units in CISO and ERCO |
| `plant_fuel_generation.csv.gz` | PUDL `out_eia923__yearly_generation_fuel_combined`, fuel for electricity and net generation |
| `N3045CA3m.xls`, `N3045TX3m.xls` | EIA natural gas price sold to electric power consumers, California and Texas, monthly |
| `EER_EPD2DC_PF4_Y05LA_DPGm.xls`, `EER_EPD2DXL0_PF4_RGC_DPGm.xls` | EIA spot diesel, Los Angeles CARB ULSD and Gulf Coast ULSD |
| `carb_auction_settlement_prices.csv` | CARB "Summary of California-Quebec Joint Auction Settlement Prices and Results" (August 2026), transcribed |

## Method

Rules fixed before looking at the results:

- **Summer** is June through October and the off-season check is December through April (paper, footnote 1 and
  section V). A summer counts only if at least 95% of its hours have an hourly price.
- **Fossil demand** is EIA-930 gas plus coal plus oil generation minus estimated cogeneration output (paper equation
  [4] with observed imports). **W** is demand less nuclear, wind, solar and cogeneration output (equation [6]).
- **Fleet** is each year's existing gas, oil and coal generators in the balancing area, summer capacity from April to
  October and winter capacity otherwise. Cogeneration units are must-take at their annual capacity factor.
- **Heat rate** is plant-by-technology fuel for electricity over net generation, pooled 2019–2025, kept between 5.5 and
  20 MMBtu/MWh and at least 500 MWh; otherwise the technology median.
- **Marginal cost** is heat rate times fuel price (gas at the state monthly price divided by EIA heat content of
  1.034 and 1.019 MMBtu/Mcf; diesel at 0.137381 MMBtu/gal; coal at each plant's reported cost) plus EPA carbon
  dioxide factors times the CARB price in California, plus EIA AEO2023 variable O&M ($2.87 combined cycle, $5.29
  turbines and steam, $6.40 engines). Three months missing from EIA's California gas series are carried forward from
  the prior month.
- **Outages** use NERC GADS 2020–2024 EFORd class averages (ISO New England table), 100 draws per day. If fossil
  demand exceeds available capacity the price is the offer cap ($1,000 in CAISO; $9,000 in ERCOT before 2022,
  $5,000 after), as the paper used the ISO price cap.
- **Prices** are the CAISO day-ahead system energy component and the ERCOT day-ahead hub average. Negative markups are
  kept, as in the paper.
- **Rent division** follows Table 3, but production cost is the expected fuel and O&M cost of in-state fossil output
  only; imports, hydro and storage enter at zero cost, so competitive rents include whatever those resources cost.
  Regulation reserve is a sensitivity, not part of the baseline as in the paper.

The benchmark and test, for hour $`t`$ and outage draw $`j`$:

```math
\begin{aligned}
\bar{P}^{c}_t &= \frac{1}{100}\sum_{j=1}^{100} C_j(q^{ff}_t), \qquad
\Delta TC_t = (P_t - \bar{P}^{c}_t)\,W_t \\
MP(S) &= \frac{\sum_{t\in S}\Delta TC_t}{\sum_{t\in S} P_t W_t}, \qquad
H_0: \mathbb{E}\Big[\textstyle\sum_{t\in S}\Delta TC_t\Big] = 0
\end{aligned}
```

The standard error follows the paper's Appendix B. The hourly markup is regressed on hour, weekday and month-of-sample
dummies and on demand and its square; residuals times $`W_t`$ are summed by day into $`Z_d`$; and

```math
\widehat{V} = \hat{g}(0) + 2\sum_{\tau=1}^{10}\Big(1 - \frac{\tau}{11}\Big)\hat{g}(\tau),
\qquad \text{SE} = \sqrt{D\,\widehat{V}}
```

where $`\hat{g}(\tau)`$ is the lag-$`\tau`$ autocovariance of $`Z_d`$ and $`D`$ the number of days.

## Test statistics

| | Rents ($M) | SE | 95% CI | MP | Off-season MP before |
|---|---|---|---|---|---|
| CAISO 2024 | 155.8 | 67.5 | [23.4, 288.2] | 5.4% | −4.6% |
| CAISO 2025 | −87.7 | 37.5 | [−161.2, −14.1] | −3.5% | −7.9% |
| ERCOT 2019 | 5,070.1 | 1,498.5 | [2,133.0, 8,007.2] | 53.4% | n/a |
| ERCOT 2020 | 385.9 | 419.0 | [−435.4, 1,207.1] | 12.4% | 22.1% |
| ERCOT 2021 | 866.5 | 423.5 | [36.4, 1,696.7] | 16.3% | 79.6% |
| ERCOT 2022 | 3,867.1 | 819.8 | [2,260.4, 5,473.9] | 34.3% | 8.9% |
| ERCOT 2023 | 13,011.1 | 2,499.7 | [8,111.6, 17,910.6] | 75.3% | 43.1% |
| ERCOT 2024 | 979.4 | 385.3 | [224.1, 1,734.7] | 26.5% | 43.5% |
| ERCOT 2025 | 1,370.3 | 334.8 | [714.0, 2,026.6] | 31.9% | 25.2% |

Pooled summer MP under the paper's alternatives (CAISO pools the August 2023 to October 2025 summer hours):

| Case | CAISO | ERCOT |
|---|---|---|
| Baseline | 1.8% | 46.9% |
| Negative markups set to zero | 12.5% | 51.0% |
| No forced outages | 7.7% | 54.2% |
| Regulation reserve at 2.2% of demand | −3.9% | 25.5% |
| Imports respond with elasticity 0.63 | 0.3% | not run |
| SP15 hub price | −4.1% | not run |

Validation of the on-peak index over 684 days: mean $34.48 against a realized SP15 on-peak LMP of $34.15 (correlation
0.96) and a system energy component of $41.02. Fossil demand exceeded available capacity in 0.041% of CAISO and 0.011%
of ERCOT hour-draws.

## Reproducing the results

```bash
pip install -r requirements.txt
python src/fetch_data.py        # optional: rebuilds data/raw/ from the sources (about 15 minutes)
python src/market_power.py      # about one minute; writes the CSVs in results/
python src/figures.py           # draws the two figures
```

## Repository layout

| Path | What it is |
|---|---|
| [src/fetch_data.py](src/fetch_data.py) | Downloads and slims the public inputs |
| [src/market_power.py](src/market_power.py) | Fleet, benchmark, Monte Carlo, rent division, standard errors, sensitivities |
| [src/figures.py](src/figures.py) | The two figures |
| `data/raw/` | Committed slim inputs (about 5 MB) |
| `results/` | CSV tables, two figures, FINDINGS.md |

## References

- Borenstein, S., Bushnell, J. B. & Wolak, F. A. (2002). Measuring market inefficiencies in California's restructured
  wholesale electricity market. *American Economic Review* 92(5).
- California ISO, CPUC & CEC (2021). Final root cause analysis, mid-August 2020 extreme heat wave.
- EIA (2023). Cost and performance characteristics of new generating technologies, *Annual Energy Outlook 2023*.
- California ISO Department of Market Monitoring (2020). Report on system and market conditions, issues and
  performance, August and September 2020.
- Public Utility Commission of Texas (2021). Amendments to 16 TAC §25.505 setting the high system-wide offer cap at
  $5,000 per MWh from January 1, 2022.
- NERC Generating Availability Data System, EFORd class averages 2020–2024, as tabulated by ISO New England (2026).
- Rajaraman, R. & Alvarado, F. L. (2002, rev. 2003). (Dis)proving market power. Laurits R. Christensen Associates.
