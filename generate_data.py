import pandas as pd
import numpy as np
from datetime import datetime

# 1. Configuration
product_map = {
    'Franchise A': ['Brand A', 'Brand B', 'Brand C'],
    'Franchise B': ['Brand D', 'Brand E', 'Brand F'],
    'Franchise C': ['Brand G']
}

# Country: (Region, Cluster, Currency, FX_Rate_to_1_USD)
geo_data = {
    'USA': ('North America', 'US/CAN', 'USD', 1.0),
    'Canada': ('North America', 'US/CAN', 'CAD', 1.36),
    'Brazil': ('LATAM', 'Southern Cone', 'BRL', 5.10),
    'Mexico': ('LATAM', 'Southern Cone', 'MXN', 18.20),
    'Singapore': ('APAC', 'SE Asia', 'SGD', 1.35),
    'India': ('APAC', 'SE Asia', 'INR', 83.50),
    'Australia': ('APAC', 'Oceania', 'AUD', 1.52),
    'UK': ('EMEA', 'Western Europe', 'GBP', 0.78),
    'Germany': ('EMEA', 'DACH', 'EUR', 0.92),
    'UAE': ('EMEA', 'Middle East', 'AED', 3.67)
}

# 2. Generate Data
dates = pd.date_range(start='2024-01-01', end='2025-12-01', freq='MS')
rows = []

for date in dates:
    for country, (region, cluster, curr, fx) in geo_data.items():
        for franchise, brands in product_map.items():
            for brand in brands:
                base_usd = np.random.randint(5000, 20000)
                units = np.random.randint(50, 500)
                
                rows.append({
                    'Month': date.strftime('%Y-%m-%d'),
                    'Franchise': franchise,
                    'Brand': brand,
                    'Region': region,
                    'Cluster': cluster,
                    'Country': country,
                    'Currency': curr,
                    'Sales_Local': round(base_usd * fx, 2),
                    'Sales_USD': float(base_usd),
                    'Units': units,
                    'Budget_USD': round(base_usd * np.random.uniform(0.9, 1.1), 2)
                })

df = pd.DataFrame(rows)

# 3. Save to CSV
print("Number of rows generated:", len(df))
df.to_csv("sales_sample.csv", index=False)
print("CSV file created: sales_sample.csv")