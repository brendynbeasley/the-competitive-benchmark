"""Download the public inputs and write the slim copies kept in data/raw/.

The repository already ships the slim files, so this script is only needed to
rebuild them from the original sources. It downloads:

  * EIA-930 hourly balancing-authority data for CAISO (CISO) and ERCOT (ERCO)
    (eia.gov/electricity/gridmonitor), about 100 MB and 75 MB of Excel;
  * CAISO day-ahead prices for the SP15 trading hub from the OASIS API, one
    request per month, keeping the system marginal energy component (MCE).
    OASIS keeps about 39 months of history, so hourly prices start in August 2023;
  * EIA's copies of ICE day-ahead on-peak index trades for SP15 (2019-2025),
    which cover California before August 2023 at daily resolution;
  * ERCOT's "Historical DAM Load Zone and Hub Prices" yearly files;
  * PUDL's processed EIA-860/923 generator and generation-fuel tables
    (Catalyst Cooperative, release v2026.10.0);
  * EIA monthly natural gas prices to electric power consumers (California,
    Texas) and spot diesel prices (Los Angeles CARB ULSD, Gulf Coast ULSD).

The CARB allowance auction prices (data/raw/carb_auction_settlement_prices.csv)
were transcribed from CARB's "Summary of California-Quebec Joint Auction
Settlement Prices and Results" (updated August 2026) and are not re-fetched.

Usage:
    python src/fetch_data.py            # everything
    python src/fetch_data.py --skip-oasis
"""

import argparse
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DL = ROOT / "data" / "download"     # large originals, ignored by git

YEARS = list(range(2019, 2026))     # 2019-2025: full years with EIA-930 fuel detail
BAS = ["CISO", "ERCO"]
PUDL = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/v2026.10.0/"
EIA930 = "https://www.eia.gov/electricity/gridmonitor/knownissues/xls/{}.xlsx"
OASIS = ("https://oasis.caiso.com/oasisapi/SingleZip?queryname=PRC_LMP&startdatetime={}T07:00-0000"
         "&enddatetime={}T08:00-0000&version=12&market_run_id=DAM&node=TH_SP15_GEN-APND&resultformat=6")
ERCOT_LIST = "https://www.ercot.com/misapp/servlets/IceDocListJsonWS?reportTypeId=13060"
ERCOT_GET = "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId={}"
EIA_XLS = {
    "N3045CA3m.xls": "https://www.eia.gov/dnav/ng/hist_xls/N3045CA3m.xls",
    "N3045TX3m.xls": "https://www.eia.gov/dnav/ng/hist_xls/N3045TX3m.xls",
    "EER_EPD2DC_PF4_Y05LA_DPGm.xls": "https://www.eia.gov/dnav/pet/hist_xls/EER_EPD2DC_PF4_Y05LA_DPGm.xls",
    "EER_EPD2DXL0_PF4_RGC_DPGm.xls": "https://www.eia.gov/dnav/pet/hist_xls/EER_EPD2DXL0_PF4_RGC_DPGm.xls",
}
ICE = "https://www.eia.gov/electricity/wholesale/xls/archive/ice_electric-{}final.xlsx"
OASIS_FIRST = pd.Timestamp(2023, 8, 1)   # earliest month OASIS still served in November 2026
UA = {"User-Agent": "Mozilla/5.0 (research download)"}

# EIA-930 columns kept ("Adjusted" = EIA's cleaned series), renamed to short names
GEN_COLS = ["COL", "NG", "NUC", "OIL", "GEO", "WAT", "PS", "SUN", "SNB", "WND", "WNB", "BAT", "OES",
            "UES", "OTH", "UNK"]


def get(url, path=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    if path is not None:
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(data)
        tmp.rename(path)
    return data


def fetch_eia930():
    for ba in BAS:
        src = DL / f"{ba}.xlsx"
        if not src.exists():
            print(f"downloading EIA-930 {ba}")
            get(EIA930.format(ba), src)
        df = pd.read_excel(src, sheet_name="Published Hourly Data", engine="calamine")
        keep = {"Local date": "local_date", "Hour": "hour", "Adjusted demand": "demand",
                "Adjusted total interchange": "interchange"}
        keep.update({f"Adjusted {c} Gen": c.lower() for c in GEN_COLS})
        df = df[[c for c in keep if c in df.columns]].rename(columns=keep)
        df["local_date"] = pd.to_datetime(df["local_date"]).dt.date
        years = pd.to_datetime(df["local_date"]).dt.year
        n0 = len(df)
        df = df[years.isin(YEARS)]
        print(f"EIA-930 {ba}: {n0} rows loaded, {len(df)} kept in {YEARS[0]}-{YEARS[-1]}")
        df.to_csv(RAW / f"eia930_{ba}_hourly.csv.gz", index=False)


def fetch_oasis():
    frames = []
    for y in YEARS:
        for m in range(1, 13):
            first = pd.Timestamp(y, m, 1)
            if first < OASIS_FIRST:
                continue
            # OASIS serves under 31 days per request, so each month comes in two halves
            for start, end in [(first, first + pd.Timedelta(days=15)),
                               (first + pd.Timedelta(days=15), first + pd.offsets.MonthBegin(1))]:
                url = OASIS.format(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
                d = None
                for attempt in range(5):
                    try:
                        z = zipfile.ZipFile(io.BytesIO(get(url)))
                        name = [n for n in z.namelist() if n.endswith(".csv")][0]
                        d = pd.read_csv(z.open(name))
                        break
                    except Exception as e:  # OASIS throttles; wait and retry
                        print(f"  retry {start.date()}: {e}")
                        time.sleep(15)
                if d is None:
                    raise RuntimeError(f"OASIS request failed for {start.date()}")
                d = d[d["LMP_TYPE"].isin(["MCE", "LMP"])]
                d = d.pivot_table(index=["OPR_DT", "OPR_HR"], columns="LMP_TYPE", values="MW").reset_index()
                dt = pd.to_datetime(d["OPR_DT"])
                frames.append(d[(dt >= start) & (dt < end)])
                time.sleep(6)
            print(f"OASIS {y}-{m:02d} done")
    out = pd.concat(frames).rename(columns={"OPR_DT": "date", "OPR_HR": "hour", "MCE": "mce",
                                            "LMP": "lmp_sp15"})
    out = out.drop_duplicates(["date", "hour"])
    print(f"OASIS: {len(out)} hourly day-ahead prices")
    out.to_csv(RAW / "caiso_dam_prices.csv.gz", index=False)


def fetch_ercot():
    docs = json.loads(get(ERCOT_LIST))["ListDocsByRptTypeRes"]["DocumentList"]
    ids = {d["Document"]["FriendlyName"]: d["Document"]["DocID"] for d in docs}
    frames = []
    for y in YEARS:
        z = zipfile.ZipFile(io.BytesIO(get(ERCOT_GET.format(ids[f"DAMLZHBSPP_{y}"]))))
        sheets = pd.read_excel(z.open(z.namelist()[0]), sheet_name=None, engine="calamine")
        d = pd.concat(sheets.values())
        d = d[d["Settlement Point"] == "HB_HUBAVG"]
        n0 = len(d)
        d = d[d["Repeated Hour Flag"] == "N"]
        frames.append(d)
        print(f"ERCOT DAM {y}: {n0} hub-average hours, {n0 - len(d)} repeated DST hours dropped")
    out = pd.concat(frames)
    out = pd.DataFrame({"date": pd.to_datetime(out["Delivery Date"]).dt.date,
                        "hour": out["Hour Ending"].str.slice(0, 2).astype(int),
                        "price": out["Settlement Point Price"]})
    out.to_csv(RAW / "ercot_dam_hubavg.csv.gz", index=False)


def fetch_ice():
    frames = []
    for y in YEARS:
        x = pd.read_excel(io.BytesIO(get(ICE.format(y))), engine="calamine")
        x.columns = ["hub", "trade_date", "start", "end", "high", "low", "price", "change", "volume_mwh",
                     "trades", "counterparties"]
        frames.append(x[x["hub"].isin(["SP15 EZ Gen DA LMP Peak", "ERCOT North 345KV Peak"])])
    x = pd.concat(frames)
    for c in ["trade_date", "start", "end"]:
        x[c] = pd.to_datetime(x[c], format="mixed")
    rows = []
    for r in x.itertuples():   # a trade can cover several delivery days (e.g. a weekend package)
        for d in pd.date_range(r.start, r.end):
            rows.append((r.hub, d.date(), r.trade_date.date(), r.price, r.volume_mwh))
    out = pd.DataFrame(rows, columns=["hub", "date", "trade_date", "price", "volume_mwh"])
    out = out.sort_values("trade_date").drop_duplicates(["hub", "date"], keep="last").sort_values(["hub", "date"])
    print(f"ICE on-peak index: {len(x)} trades, {len(out)} hub-delivery days")
    out.to_csv(RAW / "ice_onpeak_daily.csv", index=False)


def fetch_pudl():
    for t in ["out_eia__yearly_generators", "out_eia923__yearly_generation_fuel_combined"]:
        p = DL / f"{t}.parquet"
        if not p.exists():
            print(f"downloading PUDL {t}")
            get(PUDL + f"{t}.parquet", p)
    g = pd.read_parquet(DL / "out_eia__yearly_generators.parquet")
    g["year"] = pd.to_datetime(g["report_date"]).dt.year
    n0 = len(g)
    g = g[g["balancing_authority_code_eia"].isin(BAS) & g["year"].isin(YEARS)
          & (g["operational_status"] == "existing")
          & g["fuel_type_code_pudl"].isin(["gas", "oil", "coal"])]
    cols = ["year", "balancing_authority_code_eia", "plant_id_eia", "plant_name_eia", "generator_id",
            "utility_name_eia", "prime_mover_code", "energy_source_code_1", "fuel_type_code_pudl",
            "capacity_mw", "summer_capacity_mw", "winter_capacity_mw", "associated_combined_heat_power",
            "capacity_factor", "fuel_cost_per_mmbtu"]
    g = g[cols]
    print(f"PUDL generators: {n0} rows, {len(g)} fossil generator-years in CISO/ERCO {YEARS[0]}-{YEARS[-1]}")
    g.to_csv(RAW / "fleet_generators.csv.gz", index=False)

    f = pd.read_parquet(DL / "out_eia923__yearly_generation_fuel_combined.parquet")
    f["year"] = pd.to_datetime(f["report_date"]).dt.year
    f = f[f["plant_id_eia"].isin(g["plant_id_eia"].unique()) & f["year"].isin(YEARS)
          & f["fuel_type_code_pudl"].isin(["gas", "oil", "coal"])]
    f = f.groupby(["plant_id_eia", "prime_mover_code", "year"], as_index=False)[
        ["fuel_consumed_for_electricity_mmbtu", "net_generation_mwh"]].sum()
    print(f"PUDL generation-fuel: {len(f)} plant x prime-mover x year rows")
    f.to_csv(RAW / "plant_fuel_generation.csv.gz", index=False)


def fetch_eia_prices():
    for name, url in EIA_XLS.items():
        get(url, RAW / name)
        print(f"EIA price series {name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-oasis", action="store_true")
    ap.add_argument("--oasis-only", action="store_true")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    DL.mkdir(parents=True, exist_ok=True)
    if not a.oasis_only:
        fetch_eia_prices()
        fetch_ice()
        fetch_pudl()
        fetch_eia930()
        fetch_ercot()
    if not a.skip_oasis:
        fetch_oasis()
