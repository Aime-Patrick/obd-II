import pandas as pd
import os
import glob
import json

def explore_csv(file_path):
    report = {"file": os.path.basename(file_path)}
    try:
        df = pd.read_csv(file_path, low_memory=False)
        report["shape"] = df.shape
        report["columns"] = list(df.columns)
        
        target_cols = [c for c in df.columns if 'CODE' in c.upper() or 'DTC' in c.upper()]
        report["target_columns"] = target_cols
        
        col_details = {}
        for col in target_cols:
            non_empty = df[col].dropna()
            if len(non_empty) > 0:
                col_details[col] = {
                    "count": len(non_empty),
                    "unique_count": int(non_empty.nunique()),
                    "samples": non_empty.head(20).tolist(),
                    "top_values": non_empty.value_counts().head(10).to_dict()
                }
        report["details"] = col_details
        return report
                
    except Exception as e:
        return {"file": os.path.basename(file_path), "error": str(e)}

if __name__ == "__main__":
    archive_path = "d:/Project/vehicle-diagnostic-with-OBD_2/archive"
    csv_files = glob.glob(os.path.join(archive_path, "*.csv"))
    full_report = []
    for f in csv_files:
        full_report.append(explore_csv(f))
    
    with open("ml/data_report.json", "w") as f:
        json.dump(full_report, f, indent=4)
    print("Report written to ml/data_report.json")
