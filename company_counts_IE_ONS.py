import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from io import BytesIO
import httpx
import zipfile
import io
import matplotlib.pyplot as plt
import numpy as np

###############################################################################
# SETTINGS
###############################################################################

DATASET_PAGE = "https://www.ons.gov.uk/businessindustryandtrade/business/activitysizeandlocation/datasets/ukbusinessactivitysizeandlocation"

ITL1_NAMES = {
    "E12000001": "North East",
    "E12000002": "North West",
    "E12000003": "Yorkshire and The Humber",
    "E12000004": "East Midlands",
    "E12000005": "West Midlands",
    "E12000006": "East of England",
    "E12000007": "London",
    "E12000008": "South East",
    "E12000009": "South West",
    "W92000004": "Wales",
    "S92000003": "Scotland",
    "N92000002": "Northern Ireland",
}

TL_TO_ONS = {
    "TLC":"E12000001","TLD":"E12000002","TLE":"E12000003",
    "TLF":"E12000004","TLG":"E12000005","TLH":"E12000006",
    "TLI":"E12000007","TLJ":"E12000008","TLK":"E12000009",
    "TLL":"W92000004","TLM":"S92000003","TLN":"N92000002",
}

UK_TOTAL_CODE = "K02000001"
EXCLUDED_CODES = {"K03000001","K04000001","E92000001"}

###############################################################################
# 1. DOWNLOAD ONS DATA
###############################################################################

print("Fetching ONS dataset page...")
response = requests.get(DATASET_PAGE)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
excel_link = next(
    link["href"] for link in soup.find_all("a", href=True)
    if link["href"].endswith(".xlsx")
)

if not excel_link.startswith("http"):
    excel_link = "https://www.ons.gov.uk" + excel_link

excel_response = requests.get(excel_link)
excel_response.raise_for_status()

excel_file = BytesIO(excel_response.content)
xls = pd.ExcelFile(excel_file)

###############################################################################
# 2. TABLE 2 (SIC4 × REGION TOTALS)
###############################################################################

df_ons = pd.read_excel(xls, sheet_name="Table 2", header=None)
df_ons = df_ons.iloc[3:].reset_index(drop=True)
df_ons.columns = df_ons.iloc[0]
df_ons = df_ons.iloc[1:].reset_index(drop=True)

df_ons.columns = [str(c).split(":")[0].strip() for c in df_ons.columns]
df_ons.columns.values[0] = "SICs"

df_ons["SICs"] = (
    df_ons["SICs"]
    .astype(str)
    .str.strip()
    .str.extract(r"^(\d{4})")
)

df_ons = df_ons[df_ons["SICs"].notna()]
df_ons.iloc[:,1:] = df_ons.iloc[:,1:].apply(pd.to_numeric, errors="coerce")

###############################################################################
# 3. TABLE 3 (SIC2 + EMPLOYMENT BANDS)
###############################################################################

row4 = pd.read_excel(xls, sheet_name="Table 3", header=None, nrows=4)
region_row = row4.iloc[3]

region_codes = [
    str(v).split(":")[0].strip()
    for v in region_row
    if isinstance(v,str) and ":" in v
]

region_codes = [r for r in region_codes if r not in EXCLUDED_CODES]

df_t3 = pd.read_excel(xls, sheet_name="Table 3", header=4)
df_t3 = df_t3.rename(columns={df_t3.columns[0]:"SICs"})
df_t3["SICs"] = df_t3["SICs"].astype(str).str.strip()

# SIC2 totals
total_cols = [c for c in df_t3.columns if str(c).strip()=="Total"]
df_sic2 = df_t3[["SICs"] + total_cols].copy()
df_sic2.columns = ["SICs"] + region_codes[:len(total_cols)]

df_sic2["SIC2"] = df_sic2["SICs"].str.extract(r"^(\d{2})")
df_sic2 = df_sic2[df_sic2["SICs"].str.lower()!="total"]

for col in region_codes:
    if col in df_sic2.columns:
        df_sic2[col] = pd.to_numeric(df_sic2[col], errors="coerce")

# Employment band totals (row "Total")
band_row = df_t3[df_t3["SICs"].str.lower()=="total"].iloc[0]
band_names = ["0-4","5-9","10-19","20-49","50-99","100-249","250+"]

band_data = []
idx = 1
for region in region_codes:
    for band in band_names:
        band_data.append([
            region,
            band,
            pd.to_numeric(band_row.iloc[idx], errors="coerce")
        ])
        idx += 1

df_band_ons = pd.DataFrame(band_data, columns=["Region","Band","ONS"])

###############################################################################
# 4. DOWNLOAD PLATFORM DATA
###############################################################################

url = "https://serverjan26.thedatacity.com/api/downloadlist"

payload = {
    "OrderBy":"SectorKeywordCount",
    "Order":"desc",
    "DownloadFormat":"csv",
    "ReturnCount":5000000,
    "DownloadFields":[
        "Companynumber",
        "ITL1Code",
        "SICs",
        "BestEstimateUKEmployees"
    ],
    "CompanyStatusList":["Active"],
}

with httpx.Client(timeout=None) as client:
    resp = client.post(url, json=payload)
    resp.raise_for_status()
    meta = resp.json()

    download_url = "https://serverjan26.thedatacity.com" + meta["Download_URL"]

    with client.stream("GET", download_url) as r:
        zip_buffer = io.BytesIO()
        for chunk in r.iter_bytes():
            zip_buffer.write(chunk)

zip_buffer.seek(0)

with zipfile.ZipFile(zip_buffer) as z:
    df_comp = pd.read_csv(z.open("Companies.csv"), dtype=str)
    df_loc = pd.read_csv(z.open("Locations.csv"), dtype=str)

companydata = df_comp.merge(df_loc,on="Companynumber",how="left")

###############################################################################
# CLEAN PLATFORM DATA
###############################################################################

companydata = companydata[
    ~companydata["SICs"].astype(str).str.contains(r"\b99999\b",na=False)
]

companydata["Region"] = companydata["ITL1Code"].map(TL_TO_ONS)
companydata = companydata.dropna(subset=["Region"])

companydata["SICs"] = companydata["SICs"].fillna("").str.split(",")
companydata = companydata.explode("SICs")
companydata["SICs"] = companydata["SICs"].str.strip()

companydata["SIC2"] = companydata["SICs"].str.extract(r"^(\d{2})")
companydata["BestEstimateUKEmployees"] = pd.to_numeric(
    companydata["BestEstimateUKEmployees"], errors="coerce"
)

###############################################################################
# SERVER VERSION
###############################################################################

server_version = re.search(r"server([a-z0-9]+)", url).group(1)

###############################################################################
# UK TOTAL BAR CHART
###############################################################################

total_platform = companydata["Companynumber"].nunique()
total_platform_emp1 = companydata[
    companydata["BestEstimateUKEmployees"]>=1
]["Companynumber"].nunique()

total_ons = df_ons[UK_TOTAL_CODE].sum()

labels = [
    "Industry Engine (All)",
    "ONS (PAYE/VAT companies)",
    "Industry Engine (Employees ≥1)"
]

values = [total_platform,total_ons,total_platform_emp1]

plt.figure()
bars = plt.bar(labels,values)
plt.title("Total Number of UK Companies")
plt.xticks(rotation=20)

for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x()+bar.get_width()/2,height,
             f"{int(height):,}",ha="center",va="bottom", fontsize=7)

plt.tight_layout()
plt.savefig(f"uk_total_company_counts_{server_version}.png",dpi=300)
plt.show()

###############################################################################
# ITL1 REGION COMPARISON
###############################################################################

regions = list(ITL1_NAMES.keys())

ons_region_totals = df_ons[regions].sum()

platform_region_totals = (
    companydata.groupby("Region")["Companynumber"]
    .nunique().reindex(regions,fill_value=0)
)

platform_emp1_region_totals = (
    companydata[companydata["BestEstimateUKEmployees"]>=1]
    .groupby("Region")["Companynumber"]
    .nunique().reindex(regions,fill_value=0)
)

x = np.arange(len(regions))
w = 0.25

plt.figure(figsize=(14,6))
bars1 = plt.bar(x-w,platform_region_totals.values,w,
                label="Industry Engine (All)")
bars2 = plt.bar(x,ons_region_totals.values,w,
                label="ONS (PAYE/VAT companies)")
bars3 = plt.bar(x+w,platform_emp1_region_totals.values,w,
                label="Industry Engine (Employees ≥1)")

plt.title("Number of UK Companies by ITL1 region")
plt.xticks(x,[ITL1_NAMES[r] for r in regions],rotation=45,ha="right")
plt.legend()
plt.tight_layout()
plt.savefig(f"company_counts_by_ITL1_region_{server_version}.png",dpi=300)
plt.show()

###############################################################################
# SIC2 SCATTER (LOG-LOG)
###############################################################################

ons_sic2_uk = df_sic2[["SIC2",UK_TOTAL_CODE]].rename(
    columns={UK_TOTAL_CODE:"ONS_UK"}
)

platform_sic2_all = (
    companydata.groupby("SIC2")["Companynumber"]
    .nunique().reset_index()
    .rename(columns={"Companynumber":"Platform_All"})
)

platform_sic2_emp1 = (
    companydata[companydata["BestEstimateUKEmployees"]>=1]
    .groupby("SIC2")["Companynumber"]
    .nunique().reset_index()
    .rename(columns={"Companynumber":"Platform_Emp1"})
)

sic2_compare = ons_sic2_uk.merge(platform_sic2_all,on="SIC2",how="left")
sic2_compare = sic2_compare.merge(platform_sic2_emp1,on="SIC2",how="left")
sic2_compare = sic2_compare.fillna(0)

sic2_all = sic2_compare[
    (sic2_compare["ONS_UK"]>0) &
    (sic2_compare["Platform_All"]>0)
]

sic2_emp1 = sic2_compare[
    (sic2_compare["ONS_UK"]>0) &
    (sic2_compare["Platform_Emp1"]>0)
]

plt.figure()

plt.scatter(
    sic2_all["ONS_UK"],
    sic2_all["Platform_All"],
    label="Industry Engine (All)",
    alpha=0.7
)

plt.scatter(
    sic2_emp1["ONS_UK"],
    sic2_emp1["Platform_Emp1"],
    label="Industry Engine (Employees ≥1)",
    alpha=0.7
)

plt.xscale("log")
plt.yscale("log")

plt.xlabel("ONS UK Company Counts (log scale)")
plt.ylabel("Industry Engine UK Company Counts (log scale)")
plt.title("SIC2 Company Counts: ONS vs Industry Engine")

min_val = min(sic2_compare["ONS_UK"].min(),
              sic2_compare["Platform_All"].min())
max_val = max(sic2_compare["ONS_UK"].max(),
              sic2_compare["Platform_All"].max())

plt.plot([min_val,max_val],[min_val,max_val])

plt.legend()
plt.tight_layout()
plt.savefig(f"sic2_scatter_platform_vs_ons_{server_version}.png",dpi=300)
plt.show()

###############################################################################
# EMPLOYMENT BAND COMPARISON (UK)
###############################################################################

bins = [-1,4,9,19,49,99,249,999999]
companydata["Band"] = pd.cut(
    companydata["BestEstimateUKEmployees"],
    bins=bins,
    labels=band_names
)

platform_band_uk = (
    companydata.groupby("Band")["Companynumber"]
    .nunique().reset_index()
    .rename(columns={"Companynumber":"Platform"})
)

ons_band_uk = df_band_ons[df_band_ons["Region"]==UK_TOTAL_CODE]

band_compare = ons_band_uk.merge(
    platform_band_uk,on="Band",how="left"
).fillna(0)

x = np.arange(len(band_compare))
w = 0.35

plt.figure(figsize=(10,5))

bars1 = plt.bar(
    x-w/2,
    band_compare["ONS"],
    w,
    label="ONS (PAYE/VAT companies)"
)

bars2 = plt.bar(
    x+w/2,
    band_compare["Platform"],
    w,
    label="Industry Engine"
)

plt.xticks(x, band_compare["Band"])
plt.yscale("log")  # <-- LOG SCALE
plt.title("UK Company Counts by Employment Band (Log Scale)")
plt.ylabel("Number of Companies (log scale)")
plt.legend()

# Slight lift for labels in log space
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            plt.text(
                bar.get_x()+bar.get_width()/2,
                height * 1.05,   # small lift for log scale
                f"{int(height):,}",
                ha="center",
                va="bottom",
                fontsize=7
            )

plt.tight_layout()
plt.savefig(
    f"employment_band_comparison_uk_logscale_{server_version}.png",
    dpi=300
)
plt.show()