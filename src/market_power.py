"""Borenstein, Bushnell & Wolak (2002) on 2019-2025 data: CAISO, with ERCOT as the extension.

For every hour, build the price a perfectly competitive market would have set:
stack each in-market fossil generator by marginal cost (heat rate x fuel price,
plus variable O&M and, in California, the carbon allowance cost), knock units
out at random with their NERC forced-outage rates (100 draws), and read off the
cost of the last unit needed to meet the demand left for fossil plants after
observed nuclear, renewables, hydro, storage and net imports. Then compare it
with the day-ahead market price and add up the difference, as in BBW's
equations [4]-[7], their Table 2 (monthly) and Table 3 (summer rent division).

Usage:
    python src/market_power.py              # both markets, all sensitivities
    python src/market_power.py --quick      # 20 draws, no sensitivities
    python src/figures.py                   # then draw the two figures from results/
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "results"

YEARS = list(range(2019, 2026))
SUMMER = [6, 7, 8, 9, 10]            # BBW footnote 1: "summer" is June through October
OFFPEAK = [12, 1, 2, 3, 4]           # BBW's low-demand credibility months, December-April
NDRAW = 100                          # BBW: 100 Monte Carlo outage draws per hour
SEED = 2002
HAC_LAGS = 10                        # BBW Appendix B: Bartlett kernel, q = 10 days
IMPORT_ELASTICITY = 0.63             # BBW section V: median arc elasticity of import supply
REG_SHARE = 0.022                    # BBW fn 21: upward regulation averaged 2.2% of demand
MMBTU_PER_GAL_DIESEL = 0.137381      # EIA Btu conversion table, diesel fuel
CO2_T_PER_MMBTU = {"gas": 0.05306, "oil": 0.07396, "coal": 0.09552}  # EPA 40 CFR 98 Table C-1
# Variable O&M, 2022$/MWh, EIA AEO2023 "Cost and Performance Characteristics", Table 1
VOM = {"CC": 2.87, "GT": 5.29, "IC": 6.40, "ST": 5.29, "OT": 5.29}
OIL_CODES = {"DFO", "JF", "KER", "RFO", "WO"}
MARKETS = {
    "CAISO": dict(ba="CISO", gas="N3045CA3m.xls", btu_per_cf=1.034,   # EIA heat content, CA, 2022
                  oil="EER_EPD2DC_PF4_Y05LA_DPGm.xls", carbon=True,
                  cap={y: 1000.0 for y in YEARS}),                    # FERC Order 831 soft offer cap
    "ERCOT": dict(ba="ERCO", gas="N3045TX3m.xls", btu_per_cf=1.019,   # EIA heat content, TX, 2022
                  oil="EER_EPD2DXL0_PF4_RGC_DPGm.xls", carbon=False,      # PUCT high offer cap: $9,000, $5,000 from 2022
                  cap={y: 9000.0 if y < 2022 else 5000.0 for y in YEARS}),
}


def nerc_efor(group, mw, fuel):
    """NERC GADS EFORd class averages, 2020-2024, as tabulated by ISO New England (March 2026)."""
    if group == "CC":
        return 0.0491
    if group == "IC":
        return 0.0632
    if group in ("GT", "OT"):
        return 0.1591 if mw < 20 else (0.1083 if mw < 50 else 0.0902)
    if fuel == "coal":
        return 0.0897 if mw < 100 else 0.1023 if mw < 200 else 0.0907 if mw < 300 else 0.1399 if mw < 600 else 0.1111
    return 0.2041 if mw < 100 else 0.1126 if mw < 200 else 0.0984 if mw < 300 else 0.1007


def pm_group(pm):
    return {"CT": "CC", "CA": "CC", "CS": "CC", "CC": "CC", "GT": "GT", "IC": "IC", "ST": "ST"}.get(pm, "OT")


def eia_monthly(name):
    d = pd.read_excel(RAW / name, sheet_name="Data 1", skiprows=2, engine="calamine")
    d.columns = ["date", "value"]
    d["ym"] = pd.to_datetime(d["date"]).dt.to_period("M")
    v = d.dropna().set_index("ym")["value"]
    months = pd.period_range("2019-01", "2025-12", freq="M")
    missing = months.difference(v.index)
    if len(missing):
        print(f"{name}: {len(missing)} months missing, carried forward from the prior month")
    return v.reindex(v.index.union(months)).ffill().reindex(months)


def carbon_by_month():
    """Each month uses the settlement price of the most recent quarterly CARB auction."""
    c = pd.read_csv(RAW / "carb_auction_settlement_prices.csv")
    c["ym"] = pd.PeriodIndex.from_fields(year=c["auction_year"], month=c["auction_month"], freq="M")
    s = c.set_index("ym")["current_settlement_price_usd_per_tonne"]
    months = pd.period_range("2019-01", "2025-12", freq="M")
    return s.reindex(s.index.union(months)).ffill().reindex(months)


def build_fleet(cfg):
    g = pd.read_csv(RAW / "fleet_generators.csv.gz")
    g = g[g["balancing_authority_code_eia"] == cfg["ba"]].copy()
    g["group"] = g["prime_mover_code"].map(pm_group)
    g["fuel"] = np.where(g["energy_source_code_1"].isin(OIL_CODES), "oil", g["fuel_type_code_pudl"])
    # Heat rates: plant x technology, pooled over 2019-2025 EIA-923 fuel and generation
    f = pd.read_csv(RAW / "plant_fuel_generation.csv.gz")
    f["group"] = f["prime_mover_code"].map(pm_group)
    hr = f.groupby(["plant_id_eia", "group"])[["fuel_consumed_for_electricity_mmbtu", "net_generation_mwh"]].sum()
    hr = hr[hr["net_generation_mwh"] >= 500]
    hr = (hr["fuel_consumed_for_electricity_mmbtu"] / hr["net_generation_mwh"]).rename("heat_rate")
    hr = hr[(hr >= 5.5) & (hr <= 20)]
    g = g.merge(hr.reset_index(), on=["plant_id_eia", "group"], how="left")
    has = g["heat_rate"].notna()
    med = g[has].groupby("group")["heat_rate"].median()
    g["heat_rate"] = g["heat_rate"].fillna(g["group"].map(med)).fillna(g.loc[has, "heat_rate"].median())
    chp = g["associated_combined_heat_power"].astype(str).str.lower() == "true"
    g["chp"] = chp
    cf = g["capacity_factor"].clip(0, 1)
    g["chp_cf"] = cf.fillna(cf[chp].median())
    g["coal_cost"] = g["fuel_cost_per_mmbtu"].where(g["fuel"] == "coal")
    g["coal_cost"] = g["coal_cost"].fillna(g.groupby("year")["coal_cost"].transform("median"))
    print(f"{cfg['ba']} fleet: {len(g)} fossil generator-years; heat rate from own plant data for "
          f"{has.mean():.0%} of rows ({g.loc[has, 'capacity_mw'].sum() / g['capacity_mw'].sum():.0%} of MW), "
          f"technology median for the rest; {chp.sum()} CHP generator-years treated as must-take")
    return g


def month_stack(g, year, month, gas_price, oil_price, co2):
    """Marginal cost, capacity and forced-outage rate of each dispatchable unit for one month."""
    u = g[g["year"] == year]
    cap_col = "summer_capacity_mw" if 4 <= month <= 10 else "winter_capacity_mw"
    cap = u[cap_col].fillna(u["capacity_mw"]).clip(lower=0)
    fuel_price = np.select([u["fuel"] == "gas", u["fuel"] == "oil"], [gas_price, oil_price], u["coal_cost"])
    mc = u["heat_rate"] * (fuel_price + co2 * u["fuel"].map(CO2_T_PER_MMBTU)) + u["group"].map(VOM)
    chp_mw = float((cap * u["chp_cf"])[u["chp"]].sum())
    s = pd.DataFrame({"plant": u["plant_name_eia"], "owner": u["utility_name_eia"], "group": u["group"],
                      "heat_rate": u["heat_rate"], "fuel_price": fuel_price, "mc": mc, "cap": cap,
                      "efor": [nerc_efor(gr, c, fu) for gr, c, fu in zip(u["group"], cap, u["fuel"])]})
    s = s[(~u["chp"].values) & (s["cap"] > 0)].sort_values("mc").reset_index(drop=True)
    return s, chp_mw


def simulate(h, stacks, caps, ndraw, rng, no_outage=False):
    """BBW eq. [1] and [5]: expected marginal cost and production cost of meeting q_ff in each hour."""
    pcomp = np.empty(len(h))
    pcost = np.empty(len(h))
    short = np.zeros(len(h))
    for (ym, day), idx in h.groupby(["ym", "local_date"]).indices.items():
        s = stacks[ym]
        mc, cap, cap_price = s["mc"].values, s["cap"].values, caps[ym.year]
        avail = np.ones((1, len(mc)), bool) if no_outage else rng.random((ndraw, len(mc))) >= s["efor"].values
        mw = avail * cap
        cumcap = np.cumsum(mw, axis=1)
        cumcost = np.cumsum(mw * mc, axis=1)
        q = h["q_ff"].values[idx]
        p_draw = np.empty((len(avail), len(q)))
        c_draw = np.empty((len(avail), len(q)))
        for j in range(len(avail)):
            k = np.searchsorted(cumcap[j], q)            # first unit whose cumulative MW covers q
            over = k >= len(mc)
            kk = np.minimum(k, len(mc) - 1)
            prev_cap = np.where(kk > 0, cumcap[j][kk - 1], 0.0)
            prev_cost = np.where(kk > 0, cumcost[j][kk - 1], 0.0)
            p_draw[j] = np.where(over, cap_price, mc[kk])
            c_draw[j] = np.where(over, cumcost[j][-1] + (q - cumcap[j][-1]) * cap_price,
                                 prev_cost + (q - prev_cap) * mc[kk])
            short[idx] += over / len(avail)
        pcomp[idx] = p_draw.mean(axis=0)
        pcost[idx] = c_draw.mean(axis=0)
    return pcomp, pcost, short


def load_hours(name, cfg, g):
    e = pd.read_csv(RAW / f"eia930_{cfg['ba']}_hourly.csv.gz", parse_dates=["local_date"])
    if name == "CAISO":
        p = pd.read_csv(RAW / "caiso_dam_prices.csv.gz", parse_dates=["date"]).rename(columns={"mce": "price"})
    else:
        p = pd.read_csv(RAW / "ercot_dam_hubavg.csv.gz", parse_dates=["date"])
    p = p.drop_duplicates(["date", "hour"])
    if "lmp_sp15" not in p:
        p["lmp_sp15"] = p["price"]
    h = e.merge(p[["date", "hour", "price", "lmp_sp15"]], left_on=["local_date", "hour"], right_on=["date", "hour"], how="left")
    ice = pd.read_csv(RAW / "ice_onpeak_daily.csv", parse_dates=["date"])
    ice = ice[ice["hub"] == "SP15 EZ Gen DA LMP Peak"][["date", "price"]].rename(columns={"price": "ice", "date": "d"})
    h = h.drop(columns="date").merge(ice, left_on="local_date", right_on="d", how="left").drop(columns="d")
    if name != "CAISO":
        h["ice"] = np.nan
    n0 = len(h)
    for c in ["nuc", "sun", "snb", "wnd", "wnb", "col", "oil", "ng"]:
        h[c] = h[c].fillna(0) if c in h else 0.0
    h = h.dropna(subset=["demand"])
    print(f"{name}: {n0} EIA-930 hours, {n0 - len(h)} dropped for missing demand; {h['price'].notna().sum()} "
          f"with an hourly day-ahead price ({h.loc[h['price'].notna(), 'local_date'].min():%Y-%m} on)")
    h["ym"] = h["local_date"].dt.to_period("M")
    h["year"], h["month"] = h["local_date"].dt.year, h["local_date"].dt.month
    # Western on-peak block: hours ending 7-22, Monday-Saturday
    h["onpeak"] = h["hour"].between(7, 22) & (h["local_date"].dt.day_of_week <= 5)
    return h.reset_index(drop=True)


def hac_se(h, mkup):
    """BBW Appendix B: residual of hourly markup on calendar dummies and demand, daily sums, Bartlett q=10."""
    X = pd.get_dummies(pd.DataFrame({"hr": h["hour"].astype(str), "dow": h["local_date"].dt.day_of_week.astype(str),
                                     "ym": h["ym"].astype(str)}), drop_first=True).astype(float)
    X["load"], X["load2"] = h["demand"] / 1e4, (h["demand"] / 1e4) ** 2
    eps = sm.OLS(mkup, sm.add_constant(X)).fit().resid
    z = (eps * h["W"]).groupby(h["local_date"]).sum()
    return z


def bartlett_se(z):
    z = z.values
    n = len(z)
    v = (z @ z) / n
    for tau in range(1, HAC_LAGS + 1):
        v += 2 * (1 - tau / (HAC_LAGS + 1)) * (z[tau:] @ z[:-tau]) / n
    return np.sqrt(n * v)


def run_market(name, cfg, ndraw, sens):
    g = build_fleet(cfg)
    h = load_hours(name, cfg, g)
    gas = eia_monthly(cfg["gas"]) / cfg["btu_per_cf"]          # $/Mcf -> $/MMBtu
    oil = eia_monthly(cfg["oil"]) / MMBTU_PER_GAL_DIESEL        # $/gal -> $/MMBtu
    co2 = carbon_by_month() if cfg["carbon"] else pd.Series(0.0, index=pd.period_range("2019-01", "2025-12", freq="M"))
    stacks, chp = {}, {}
    for ym in sorted(h["ym"].unique()):
        stacks[ym], chp[ym] = month_stack(g, ym.year, ym.month, gas[ym], oil[ym], co2[ym])
    h["chp"] = h["ym"].map(chp)
    h["avail_mw"] = h["ym"].map({ym: float((st["cap"] * (1 - st["efor"])).sum()) for ym, st in stacks.items()})
    h["thermal"] = h["ng"] + h["col"] + h["oil"]
    h["q_ff"] = (h["thermal"] - h["chp"]).clip(lower=0)            # BBW eq. [4] with observed imports
    h["W"] = h["demand"] - h[["nuc", "sun", "snb", "wnd", "wnb"]].sum(axis=1) - np.minimum(h["chp"], h["thermal"])
    h["tight"] = h["q_ff"] / h["avail_mw"]                       # fossil demand / expected available MW
    h["gas_price"] = h["ym"].map(gas)
    h["co2_price"] = h["ym"].map(co2)
    rng = np.random.default_rng(SEED)
    h["pcomp"], h["pcost"], h["short"] = simulate(h, stacks, cfg["cap"], ndraw, rng)
    print(f"{name}: share of hour-draws where fossil demand exceeded available capacity: {h['short'].mean():.4%}")
    h["dTC"] = (h["price"] - h["pcomp"]) * h["W"]                  # BBW eq. [6]; NaN without a price
    h["TC"] = h["price"] * h["W"]

    # Marginal plant in each hour of the no-outage stack, for the names table
    det = h[["ym", "local_date", "q_ff"]].copy()
    marg = []
    for ym, idx in det.groupby("ym").indices.items():
        s = stacks[ym]
        k = np.minimum(np.searchsorted(np.cumsum(s["cap"].values), det["q_ff"].values[idx]), len(s) - 1)
        marg.append(pd.DataFrame({"i": idx, "plant": s["plant"].values[k], "owner": s["owner"].values[k]}))
    marg = pd.concat(marg).set_index("i").sort_index()
    h["marginal_plant"], h["marginal_owner"] = marg["plant"], marg["owner"]

    sens_rows = []
    if sens:
        base = h[h["month"].isin(SUMMER) & h["price"].notna()]
        sens_rows.append(("Baseline (BBW rules)", base["dTC"].sum() / base["TC"].sum()))
        trunc = base["dTC"].clip(lower=0).sum() / base["TC"].sum()
        sens_rows.append(("Negative markups set to zero", trunc))
        if name == "CAISO":
            lmp = ((base["lmp_sp15"] - base["pcomp"]) * base["W"]).sum() / (base["lmp_sp15"] * base["W"]).sum()
            sens_rows.append(("SP15 hub price instead of system energy price", lmp))
        for label, kw, qadj in [("No forced outages", dict(no_outage=True), 0.0),
                                ("Add regulation reserve, 2.2% of demand", {}, REG_SHARE)]:
            hh = h.copy()
            hh["q_ff"] = hh["q_ff"] + qadj * hh["demand"]
            pc, _, _ = simulate(hh, stacks, cfg["cap"], ndraw if not kw else 1, np.random.default_rng(SEED), **kw)
            m = hh["month"].isin(SUMMER) & hh["price"].notna()
            sens_rows.append((label, ((hh["price"] - pc) * hh["W"])[m].sum() / hh["TC"][m].sum()))
        if name == "CAISO":
            hh = h.copy()
            imports = hh["interchange"].clip(upper=0).abs().fillna(0)  # EIA sign: negative = net imports
            pc = hh["pcomp"].values
            for _ in range(3):                                # BBW Fig. 2: fewer imports at the competitive price
                ratio = np.clip(pc / hh["price"].clip(lower=1).values, 0, 1)
                hh["q_ff"] = h["q_ff"] + imports * (1 - ratio ** IMPORT_ELASTICITY)
                pc, _, _ = simulate(hh, stacks, cfg["cap"], ndraw, np.random.default_rng(SEED))
            m = hh["month"].isin(SUMMER) & hh["price"].notna()
            sens_rows.append(("Imports respond to price, elasticity 0.63",
                              ((hh["price"] - pc) * hh["W"])[m].sum() / hh["TC"][m].sum()))
    return h, g, stacks, sens_rows


def rent_row(s, name, label, price_col, z=None):
    """BBW Table 3 for one set of hours: payments, competitive payments, cost, rents."""
    actual = (s[price_col] * s["W"]).sum()
    comp = (s["pcomp"] * s["W"]).sum()
    row = dict(market=name, summer=label, hours=len(s), avg_price=s[price_col].mean(),
               avg_pcomp=s["pcomp"].mean(), avg_gas=s["gas_price"].mean(),
               actual_payments_musd=actual / 1e6, competitive_payments_musd=comp / 1e6,
               production_cost_musd=s["pcost"].sum() / 1e6,
               competitive_rents_musd=(comp - s["pcost"].sum()) / 1e6,
               market_power_rents_musd=(actual - comp) / 1e6, MP=(actual - comp) / actual,
               avg_q_ff=s["q_ff"].mean(), avg_net_imports=-s["interchange"].mean(),
               hours_tight90=int((s["tight"] >= 0.9).sum()),
               share_mp_rents_tight90=((s[price_col] - s["pcomp"]) * s["W"])[s["tight"] >= 0.9].sum() / (actual - comp))
    if z is not None:
        row["se_market_power_rents_musd"] = bartlett_se(z[z.index.isin(s["local_date"].unique())]) / 1e6
    return row


def summarize(name, h):
    hp = h[h["price"].notna()]
    z = hac_se(hp, hp["price"] - hp["pcomp"])
    monthly = h.groupby("ym").agg(load_mwh=("W", "mean"), price=("price", "mean"), pcomp=("pcomp", "mean"),
                                  pcomp_onpeak=("pcomp", lambda s: s[h.loc[s.index, "onpeak"]].mean()),
                                  ice_onpeak=("ice", "mean"), gas=("gas_price", "mean"), co2=("co2_price", "mean"),
                                  dTC_musd=("dTC", lambda s: s.sum(min_count=1) / 1e6),
                                  TC=("TC", lambda s: s.sum(min_count=1))).reset_index()
    monthly["MP"] = monthly["dTC_musd"] * 1e6 / monthly["TC"]
    monthly = monthly.drop(columns="TC").assign(market=name)
    rows, peak = [], []
    for y in YEARS:
        s = hp[(hp["year"] == y) & hp["month"].isin(SUMMER)]
        if len(s) > 0.95 * 153 * 24:                      # complete summers only
            row = rent_row(s, name, y, "price", z)
            o = hp[(hp["local_date"] >= f"{y - 1}-12-01") & (hp["local_date"] < f"{y}-05-01")]
            row["MP_offpeak_before"] = o["dTC"].sum() / o["TC"].sum() if len(o) > 0.95 * 151 * 24 else np.nan
            rows.append(row)
        if name == "CAISO":
            s = h[(h["year"] == y) & h["month"].isin(SUMMER) & h["onpeak"] & h["ice"].notna()]
            peak.append(rent_row(s, name, y, "ice"))
    return monthly, pd.DataFrame(rows), pd.DataFrame(peak)


def ice_check(h):
    """Does the ICE on-peak index track the realized day-ahead price where both exist?"""
    s = h[h["onpeak"] & h["price"].notna() & h["ice"].notna()]
    d = s.groupby("local_date").agg(dam=("price", "mean"), lmp=("lmp_sp15", "mean"), ice=("ice", "first"))
    out = dict(days=len(d), mean_dam_mce_onpeak=d["dam"].mean(), mean_dam_lmp_sp15_onpeak=d["lmp"].mean(),
               mean_ice=d["ice"].mean(), corr_ice_lmp=d["lmp"].corr(d["ice"]),
               corr=d["dam"].corr(d["ice"]), mean_abs_gap=(d["dam"] - d["ice"]).abs().mean())
    for y in [2024, 2025]:
        t = s[(s["year"] == y) & s["month"].isin(SUMMER)]
        out[f"MP_onpeak_dam_{y}"] = ((t["price"] - t["pcomp"]) * t["W"]).sum() / (t["price"] * t["W"]).sum()
        out[f"MP_onpeak_lmp_{y}"] = ((t["lmp_sp15"] - t["pcomp"]) * t["W"]).sum() / (t["lmp_sp15"] * t["W"]).sum()
        out[f"MP_onpeak_ice_{y}"] = ((t["ice"] - t["pcomp"]) * t["W"]).sum() / (t["ice"] * t["W"]).sum()
    return pd.DataFrame([out])


def decompose(summers):
    rows = []
    for (name, kind), s in summers.groupby(["market", "kind"]):
        s = s.set_index("summer").sort_index().select_dtypes("number")
        for a, b in zip(s.index[:-1], s.index[1:]):
            d = s.loc[b] - s.loc[a]
            tot = d["actual_payments_musd"]
            rows.append(dict(market=name, kind=kind, from_summer=a, to_summer=b, change_payments_musd=tot,
                             change_production_cost_musd=d["production_cost_musd"],
                             change_competitive_rents_musd=d["competitive_rents_musd"],
                             change_market_power_musd=d["market_power_rents_musd"],
                             share_cost=d["production_cost_musd"] / tot,
                             share_rents=d["competitive_rents_musd"] / tot,
                             share_market_power=d["market_power_rents_musd"] / tot))
    return pd.DataFrame(rows)


def lerner_bins(name, h):
    s = h[h["month"].isin(SUMMER) & (h["price"] > 0)].copy()
    s["lerner"] = ((s["price"] - s["pcomp"]) / s["price"]).clip(lower=0)  # BBW fn 39: negatives set to zero
    s["period"] = np.where(s["year"] <= 2021, "early", "late")
    for p in ["early", "late"]:
        yrs = s.loc[s["period"] == p, "year"]
        if len(yrs):
            s.loc[s["period"] == p, "period"] = f"{yrs.min()}-{yrs.max()}"
    s["bin"] = (s["q_ff"] // 2500 * 2500).astype(int)
    b = s.groupby(["period", "bin"]).agg(hours=("lerner", "size"), lerner=("lerner", "mean"),
                                         price=("price", "mean"), pcomp=("pcomp", "mean")).reset_index()
    return b[b["hours"] >= 50].assign(market=name)


def names_tables(results):
    rows, marg = [], []
    for name, (h, g, stacks, _) in results.items():
        u = g[(g["year"] == 2025) & ~g["chp"]]
        cap = u.groupby("utility_name_eia")["summer_capacity_mw"].sum().sort_values(ascending=False)
        plant_mw = u.groupby(["utility_name_eia", "plant_name_eia"])["summer_capacity_mw"].sum()
        share = cap / cap.sum()
        for owner, mw in cap.head(8).items():
            p = plant_mw.loc[owner].sort_values(ascending=False)
            rows.append(dict(market=name, operator=owner, summer_mw=mw, share=mw / cap.sum(), plants=len(p),
                             largest_plant=p.index[0], largest_plant_mw=p.iloc[0]))
        rows.append(dict(market=name, operator="HHI of dispatchable fossil capacity (0-10,000)",
                         summer_mw=cap.sum(), share=float((share * 100) ** 2 @ np.ones(len(share)))))
        s = h[h["month"].isin(SUMMER) & (h["year"] >= 2022)]
        top = s.groupby(["marginal_plant", "marginal_owner"]).size().sort_values(ascending=False).head(6)
        for (plant, owner), n in top.items():
            marg.append(dict(market=name, plant=plant, operator=owner, marginal_hours=n, share_of_hours=n / len(s)))
    ex = []   # worked examples: the most frequent marginal plants, costed in one summer month
    for name, ym in [("CAISO", pd.Period("2024-08", "M")), ("ERCOT", pd.Period("2023-08", "M"))]:
        st = results[name][2][ym]
        for plant in pd.DataFrame(marg).query("market == @name")["plant"].head(2):
            r = st[st["plant"] == plant].sort_values("cap", ascending=False).iloc[0]
            ex.append(dict(market=name, month=str(ym), plant=plant, technology=r["group"], heat_rate=r["heat_rate"],
                           fuel_price=r["fuel_price"], vom=VOM[r["group"]], marginal_cost=r["mc"],
                           plant_mw=st.loc[st["plant"] == plant, "cap"].sum()))
    return pd.DataFrame(rows), pd.DataFrame(marg), pd.DataFrame(ex)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    ndraw = 20 if a.quick else NDRAW
    results, monthly, summers, sens = {}, [], [], []
    for name, cfg in MARKETS.items():
        results[name] = run_market(name, cfg, ndraw, not a.quick)
        m, s, pk = summarize(name, results[name][0])
        monthly.append(m)
        summers += [s.assign(kind="hourly day-ahead"), pk.assign(kind="on-peak ICE index")]
        if name == "CAISO":
            ice_check(results[name][0]).to_csv(OUT / "ice_vs_dayahead_check.csv", index=False)
        sens += [dict(market=name, case=c, MP_summers=v) for c, v in results[name][3]]
        h = results[name][0]
        hp = h[h["price"].notna()]
        pd.DataFrame([dict(market=name, hours=len(h), hours_with_price=len(hp), mean_price=hp["price"].mean(),
                           mean_pcomp=hp["pcomp"].mean(), hours_price_le_0=int((hp["price"] <= 0).sum()),
                           share_negative_markup=(hp["price"] < hp["pcomp"]).mean())]).to_csv(
            OUT / f"hours_{name.lower()}.csv", index=False)
    monthly, summers = pd.concat(monthly), pd.concat([x for x in summers if len(x)])
    monthly.assign(ym=monthly["ym"].astype(str)).to_csv(OUT / "monthly_benchmark.csv", index=False)
    summers["ci95_low_musd"] = summers["market_power_rents_musd"] - 1.96 * summers["se_market_power_rents_musd"]
    summers["ci95_high_musd"] = summers["market_power_rents_musd"] + 1.96 * summers["se_market_power_rents_musd"]
    summers.to_csv(OUT / "summer_rent_division.csv", index=False)
    decompose(summers).to_csv(OUT / "summer_changes.csv", index=False)
    bins = pd.concat([lerner_bins(n, r[0]) for n, r in results.items()])
    bins.to_csv(OUT / "lerner_by_residual_demand.csv", index=False)
    if sens:
        pd.DataFrame(sens).to_csv(OUT / "sensitivity.csv", index=False)
    owners, marg, ex = names_tables(results)
    ex.to_csv(OUT / "example_unit_costs.csv", index=False)
    owners.to_csv(OUT / "fleet_operators.csv", index=False)
    marg.to_csv(OUT / "marginal_plants.csv", index=False)
    print(summers[["market", "kind", "summer", "avg_price", "avg_pcomp", "actual_payments_musd",
                   "market_power_rents_musd", "se_market_power_rents_musd", "MP"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
