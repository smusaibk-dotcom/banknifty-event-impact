def convert_revenue(x):
    if pd.isna(x):
        return np.nan

    elif "T" in x:
        return float(x.replace('T',"")) * 1000

    elif 'B' in x:
        return float(x.replace('B',''))

    else:
        return float(x)