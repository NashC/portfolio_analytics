import os
import pandas as pd
from ingestion import load_schema_config, ingest_csv


def match_file_to_mapping(file_name: str, schema_config: Dict) -> Optional[Dict]:
    for institution, entry in schema_config.items():
        if isinstance(entry, dict) and "file_pattern" in entry:
            if file_name == entry["file_pattern"]:
                return institution, None, entry["mapping"]

        elif isinstance(entry, dict):
            for sub_key, sub_entry in entry.items():
                if file_name == sub_entry["file_pattern"]:
                    return institution, sub_key, sub_entry["mapping"]
    return None, None, None


def process_transactions(data_dir: str, config_path: str) -> pd.DataFrame:
    config = load_schema_config(config_path)
    all_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    all_transactions = []

    for file_name in all_files:
        file_path = os.path.join(data_dir, file_name)
        institution, subtype, mapping = match_file_to_mapping(file_name, config)

        if mapping:
            file_type = f"{institution}_{subtype}" if subtype else institution
            df = ingest_csv(file_path, mapping, file_type=file_type)
            df["institution"] = institution
            all_transactions.append(df)
        else:
            print(f"⚠️ Skipping unrecognized file: {file_name}")

    if all_transactions:
        transactions = pd.concat(all_transactions, ignore_index=True)
        return transactions
    else:
        print("❌ No transactions processed.")
        return pd.DataFrame()


def main():
    data_dir = "data"
    config_path = "config/schema_mapping.yaml"
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    transactions = process_transactions(data_dir, config_path)
    if not transactions.empty:
        transactions.to_csv(os.path.join(output_dir, "transactions_normalized.csv"), index=False)
        print("✅ Normalized transactions exported.")
    else:
        print("🚫 No data to export.")


if __name__ == "__main__":
    main()
