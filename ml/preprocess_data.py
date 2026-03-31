import pandas as pd
import numpy as np
import os
import glob

def preprocess_data(archive_path, output_path):
    print(f"Loading CSV files from {archive_path}...")
    csv_files = glob.glob(os.path.join(archive_path, "*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {archive_path}")
        return
        
    dataframes = []
    
    for file in csv_files:
        df = pd.read_csv(file, low_memory=False)
        # Standardize column names
        df.columns = [col.upper().strip().replace(' ', '_') for col in df.columns]
        
        # Add a source file column just in case we need to debug later
        df['SOURCE_FILE'] = os.path.basename(file)
        dataframes.append(df)
        print(f"Loaded {os.path.basename(file)} with shape {df.shape}")

    # Combine all dataframes
    print("Concatenating dataframes...")
    combined_df = pd.concat(dataframes, ignore_index=True)
    
    print(f"Combined shape: {combined_df.shape}")
    
    # 1. Target Formulation
    # Create a binary target 'HAS_FAULT' based on 'TROUBLE_CODES'
    # Healthy means TROUBLE_CODES is NaN, empty string, or some generic "no trouble" string (though usually it's None/NaN or empty strings)
    # The explore code showed things like "MIL is OFF0 codes" in DTC_NUMBER, but TROUBLE_CODES had actual codes like "P0133" or NaN
    # We will assume if TROUBLE_CODES has a value and it's not a known generic healthy string, it's a fault.
    print("Formulating target...")
    
    # Identify healthy states (we assume NaN or empty means healthy)
    is_healthy = combined_df['TROUBLE_CODES'].isna() | (combined_df['TROUBLE_CODES'].astype(str).str.strip() == '')
    
    # Let's treat missing as 0 (healthy), present as 1 (fault)
    combined_df['HAS_FAULT'] = np.where(is_healthy, 0, 1)
    
    print(f"Fault distribution:\n{combined_df['HAS_FAULT'].value_counts()}")
    
    # 2. Select Features
    # Identify non-predictive/meta columns to drop
    cols_to_drop = [
        'TIMESTAMP', 'TIME', 'LATITUDE', 'LONGITUDE', 'ALTITUDE', 
        'VEHICLE_ID', 'ORD', 'AQUI', 'DTC_NUMBER', 'TROUBLE_CODES', 'SOURCE_FILE',
        'TIMING_ADVANCE', # sometimes heavily missing or not relevant to pure engine fault without context, but let's see
        # We can keep TIMING_ADVANCE and EQUIV_RATIO for now, they are engine parameters.
        # We drop the direct target leakers: DTC_NUMBER, TROUBLE_CODES
    ]
    
    # Also drop meta columns that exist conditionally
    meta_cols_actual = [c for c in cols_to_drop if c in combined_df.columns]
    features_df = combined_df.drop(columns=meta_cols_actual)
    
    # 3. Handle categorical vs numeric columns
    print("Fixing data types...")
    # These are known categorical or text columns
    known_categorical = ['MARK', 'MODEL', 'FUEL_TYPE', 'AUTOMATIC']
    
    # Everything else should be coerced to numeric if possible (sensors)
    for col in features_df.columns:
        if col not in known_categorical and col != 'HAS_FAULT':
            features_df[col] = pd.to_numeric(features_df[col], errors='coerce')

    print("Encoding categorical variables...")
    categorical_cols = [c for c in known_categorical if c in features_df.columns]
    
    for col in categorical_cols:
        print(f"  Encoding {col}...")
        if features_df[col].nunique() < 20:
            features_df = pd.get_dummies(features_df, columns=[col], prefix=col, dummy_na=True)
        else:
            features_df[col], _ = pd.factorize(features_df[col])
            
    # 4. Handle Missing Values
    print("Handling missing values...")
    numeric_cols = features_df.select_dtypes(include=[np.number]).columns
    
    # Fill missing with median for each column
    for col in numeric_cols:
        if features_df[col].isnull().any():
            median_val = features_df[col].median()
            # If a column is entirely NaN (e.g., median is NaN), fill with 0
            if pd.isna(median_val):
                median_val = 0
            features_df[col] = features_df[col].fillna(median_val)
            
    # Ensure all data is numeric
    assert features_df.select_dtypes(exclude=[np.number, bool]).shape[1] == 0, "Non-numeric columns remain!"
    assert features_df.isnull().sum().sum() == 0, "NaN values remain!"
    
    # Converting booleans from get_dummies to int just to be safe
    for col in features_df.select_dtypes(include=['bool']).columns:
        features_df[col] = features_df[col].astype(int)

    # 5. Output
    print(f"Final dataset shape: {features_df.shape}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    features_df.to_csv(output_path, index=False)
    print(f"Cleaned data saved to {output_path}")

if __name__ == "__main__":
    archive_dir = "d:/Project/vehicle-diagnostic-with-OBD_2/archive"
    output_file = "d:/Project/vehicle-diagnostic-with-OBD_2/ml/cleaned_data.csv"
    preprocess_data(archive_dir, output_file)
