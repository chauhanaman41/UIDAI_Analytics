import pandas as pd
import numpy as np
import logging
import os
import json
from datetime import datetime

# Setup logging
logging.basicConfig(
    filename='errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
FILES = {
    'biometric': [
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_biometric\api_data_aadhar_biometric\api_data_aadhar_biometric_0_500000.csv',
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_biometric\api_data_aadhar_biometric\api_data_aadhar_biometric_500000_1000000.csv',
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_biometric\api_data_aadhar_biometric\api_data_aadhar_biometric_1000000_1500000.csv',
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_biometric\api_data_aadhar_biometric\api_data_aadhar_biometric_1500000_1861108.csv'
    ],
    'demographic': [
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_demographic\api_data_aadhar_demographic\api_data_aadhar_demographic_0_500000.csv',
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_demographic\api_data_aadhar_demographic\api_data_aadhar_demographic_500000_1000000.csv',
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_demographic\api_data_aadhar_demographic\api_data_aadhar_demographic_1000000_1500000.csv',
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_demographic\api_data_aadhar_demographic\api_data_aadhar_demographic_1500000_2000000.csv',
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_demographic\api_data_aadhar_demographic\api_data_aadhar_demographic_2000000_2071700.csv'
    ],
    'enrollment': [
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_enrolment\api_data_aadhar_enrolment\api_data_aadhar_enrolment_0_500000.csv',
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_enrolment\api_data_aadhar_enrolment\api_data_aadhar_enrolment_500000_1000000.csv',
        r'C:\Users\Amandeep\Downloads\uidai\api_data_aadhar_enrolment\api_data_aadhar_enrolment\api_data_aadhar_enrolment_1000000_1006029.csv'
    ]
}

CHUNK_SIZE = 50000

# Statistics for the report
stats = {
    'biometric': {'total_rows': 0, 'valid_rows': 0, 'errors': {}},
    'demographic': {'total_rows': 0, 'valid_rows': 0, 'errors': {}},
    'enrollment': {'total_rows': 0, 'valid_rows': 0, 'errors': {}}
}

def validate_date(date_str):
    """Converts date to YYYY-MM-DD. Returns NaT if invalid."""
    try:
        # Try multiple formats if necessary, but starting with standard pandas inference
        return pd.to_datetime(date_str, format='%d-%m-%Y', errors='coerce').date()
    except Exception:
        return pd.NaT

def clean_string(text):
    """Standardizes capitalization and trims whitespace."""
    if pd.isna(text):
        return text
    return str(text).strip().title()

def validate_pincode(pincode):
    """Validates 6-digit pincode."""
    if pd.isna(pincode):
        return False
    
    s_pin = str(pincode).split('.')[0] # Handle float conversion like 110001.0
    if len(s_pin) == 6 and s_pin.isdigit():
        return int(s_pin)
    return None

def validate_numeric(value):
    """Checks for negatives, NaNs, and infinities."""
    try:
        val = float(value)
        if pd.isna(val) or np.isinf(val) or val < 0:
            return None
        return val
    except (ValueError, TypeError):
        return None

def process_file_group(file_list, file_type):
    print(f"Processing {file_type} data...")
    all_chunks = []
    
    for file_path in file_list:
        print(f"  Reading {os.path.basename(file_path)}...")
        try:
            for chunk_idx, chunk in enumerate(pd.read_csv(file_path, chunksize=CHUNK_SIZE, low_memory=False)):
                # Keep track of original indices for error logging (approximate)
                global_offset = stats[file_type]['total_rows']
                
                # 1. Date Validation
                if 'date' in chunk.columns:
                    mask_invalid_date = pd.to_datetime(chunk['date'], format='%d-%m-%Y', errors='coerce').isna()
                    # Log errors
                    error_indices = chunk[mask_invalid_date].index + global_offset
                    if not error_indices.empty:
                        stats[file_type]['errors']['invalid_date'] = stats[file_type]['errors'].get('invalid_date', 0) + len(error_indices)
                        for idx in error_indices[:5]: # Log first 5 per chunk to avoid spamming
                            logging.error(f"{file_type} - Row {idx}: Invalid Date")
                    
                    chunk['date'] = pd.to_datetime(chunk['date'], format='%d-%m-%Y', errors='coerce')
                
                # 2. String Cleaning (State, District)
                for col in ['state', 'district']:
                    if col in chunk.columns:
                        chunk[col] = chunk[col].apply(clean_string)
                
                # 3. Pincode Validation
                if 'pincode' in chunk.columns:
                    valid_pins = chunk['pincode'].apply(validate_pincode)
                    mask_invalid_pin = valid_pins.isna()
                    
                    error_indices = chunk[mask_invalid_pin].index + global_offset
                    if not error_indices.empty:
                        stats[file_type]['errors']['invalid_pincode'] = stats[file_type]['errors'].get('invalid_pincode', 0) + len(error_indices)
                        for idx in error_indices[:5]:
                            logging.error(f"{file_type} - Row {idx}: Invalid Pincode")
                            
                    chunk['pincode'] = valid_pins
                
                # 4. Numeric Validation
                # Identify numeric columns based on file type
                numeric_cols = []
                if file_type == 'biometric':
                    numeric_cols = [c for c in chunk.columns if 'bio_age' in c]
                elif file_type == 'demographic':
                    numeric_cols = [c for c in chunk.columns if 'demo_age' in c]
                elif file_type == 'enrollment':
                    numeric_cols = [c for c in chunk.columns if 'age' in c]
                
                # Filter out valid columns only
                numeric_cols = [c for c in numeric_cols if c in chunk.columns]

                for col in numeric_cols:
                    valid_nums = chunk[col].apply(validate_numeric)
                    mask_invalid_num = valid_nums.isna()
                    
                    error_indices = chunk[mask_invalid_num].index + global_offset
                    if not error_indices.empty:
                        stats[file_type]['errors'][f'invalid_numeric_{col}'] = stats[file_type]['errors'].get(f'invalid_numeric_{col}', 0) + len(error_indices)
                        for idx in error_indices[:5]:
                            logging.error(f"{file_type} - Row {idx}: Invalid Numeric in {col}")
                    
                    chunk[col] = valid_nums

                # Drop rows with critical failures if needed, OR just keep them with NaNs/None
                # Requirement says "Skip malformed rows", so we drop rows where critical fields are invalid.
                # Let's assume critical fields are Date and Pincode for now, or just drop any row with NaN after validation
                
                # A stricter approach: drop rows with ANY invalid validation
                # But requirement says "Skip malformed rows but count them"
                # We already counted them. Now we drop them from the 'clean' set.
                cols_to_check = ['date', 'pincode'] + numeric_cols
                existing_cols_to_check = [c for c in cols_to_check if c in chunk.columns]
                
                clean_chunk = chunk.dropna(subset=existing_cols_to_check)
                
                stats[file_type]['total_rows'] += len(chunk)
                stats[file_type]['valid_rows'] += len(clean_chunk)
                
                all_chunks.append(clean_chunk)
                
        except Exception as e:
            logging.error(f"Failed to process file {file_path}: {str(e)}")
            print(f"Error reading {file_path}: {e}")

    if all_chunks:
        print(f"  Concatenating {file_type} chunks...")
        full_df = pd.concat(all_chunks, ignore_index=True)
        
        output_file = f'{file_type}_clean.parquet'
        print(f"  Saving to {output_file}...")
        full_df.to_parquet(output_file, index=False)
        print(f"  Saved {file_type} data.")
    else:
        print(f"  No valid data found for {file_type}.")

def main():
    print("Starting processing...")
    
    for type_name, files in FILES.items():
        process_file_group(files, type_name)
        
    # Write validation report
    with open('validation_report.json', 'w') as f:
        json.dump(stats, f, indent=4)
        
    print("Processing complete. Check validation_report.json and errors.log for details.")

if __name__ == "__main__":
    main()
