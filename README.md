# ONS vs Industry Engine Company Counts Comparison

## Overview

This script downloads official UK business statistics from the Office for National Statistics (ONS) and compares them against company-level data retrieved from the Industry Engine (The Data City platform).

The objective is to assess how Industry Engine company counts compare with ONS VAT/PAYE registered enterprise counts across:

- UK totals  
- ITL1 regions  
- 4-digit SIC codes (Table 2)  
- 2-digit SIC codes (Table 3)  
- Employment size bands (Table 3)  

The script produces structured comparison tables and publication-ready visualisations.

## Purpose

This script enables structured benchmarking of Industry Engine company counts against official ONS VAT/PAYE enterprise statistics across:

- Geography  
- Industry  
- Employment size  


## Data Sources

### 1. ONS Dataset

Dataset:  
UK Business: Activity, Size and Location

Downloaded automatically from:

https://www.ons.gov.uk/businessindustryandtrade/business/activitysizeandlocation/datasets/ukbusinessactivitysizeandlocation

The script extracts:

- Table 2  
  - Number of VAT and PAYE enterprises  
  - 4-digit SIC  
  - ITL1 regions and UK total  

- Table 3  
  - 2-digit SIC totals  
  - Employment band totals  
  - ITL1 regions and UK total  


### 2. Industry Engine (The Data City)

Data is retrieved via the platform API.

Fields used:

- Companynumber  
- ITL1Code  
- SICs  
- BestEstimateUKEmployees  

Only Active companies are included. Dormant companies (SIC 99999) excluded


## Data Processing Logic

### SIC Handling

- Platform SIC codes are 5-digit and may contain multiple codes separated by commas.
- The script:
  - Splits multiple SICs
  - Trims whitespace
  - Removes SIC 99999
  - Extracts:
    - First 4 digits (for Table 2 comparison)
    - First 2 digits (for Table 3 comparison)


### Employment Bands

Employment bands are recreated from BestEstimateUKEmployees using the same bands as the ONS:

- 0–4  
- 5–9  
- 10–19  
- 20–49  
- 50–99  
- 100–249  
- 250+  

These are directly compared with ONS data.


## Outputs

The script generates the following visualisations:

### 1. UK Total Company Counts

Bar chart comparing:

- Industry Engine (All)  
- ONS (PAYE/VAT companies)  
- Industry Engine (Employees ≥ 1)  


### 2. ITL1 Region Comparison

Grouped bar chart per ITL1 region showing:

- Industry Engine (All)  
- ONS (PAYE/VAT companies)  
- Industry Engine (Employees ≥ 1)  


### 3. SIC2 Comparison (UK)

Scatter plot (log–log scale):

- X-axis: ONS UK counts  
- Y-axis: Industry Engine UK counts  
- Agreement (45-degree) reference line  
- Two series:
  - All companies  
  - Employees ≥ 1  


### 4. Employment Band Comparison (UK)

Grouped bar chart (log-scale Y-axis):

- ONS enterprise counts  
- Industry Engine counts (reconstructed from employee estimates)


## Output Files

All plots are saved automatically.

File names include the server version dynamically extracted from the API URL, for example:

- uk_total_company_counts_jan26.png  
- company_counts_by_ITL1_region_jan26.png  
- sic2_scatter_platform_vs_ons_jan26.png  
- employment_band_comparison_uk_logscale_jan26.png  

This allows monthly automated runs without overwriting previous outputs.


