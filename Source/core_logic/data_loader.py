import pandas as pd
import os
import re # For potential stop word removal from data

# Optional: A very conservative list of stop words to remove from SearchableText
# Be careful with this, as "nagar", "road" can be part of actual office names.
# For now, we primarily rely on the address_parser to clean the *input query*.
DATA_STOP_WORDS = {'post office', 's o', 'b o', 'h o', 'g p o'} # Example if these are too noisy

def remove_data_stop_words(text, stop_words):
    if pd.isna(text):
        return ""
    # Simple regex based removal for phrases
    for sw in stop_words:
        text = re.sub(r'\b' + re.escape(sw) + r'\b', '', text, flags=re.IGNORECASE)
    return ' '.join(text.split()) # Remove extra spaces

def load_postal_data(file_path="data/postal_data.csv"):
    """
    Loads the postal data, creates 'SearchableText', and 'OfficeName_normalized'.
    Optionally cleans 'SearchableText' from a small set of data-specific stop words.
    """
    try:
        if not os.path.exists(file_path):
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path_alt = os.path.join(script_dir, file_path)
            if os.path.exists(file_path_alt):
                file_path = file_path_alt
            else:
                print(f"Error: Data file not found at {file_path} or {file_path_alt}")
                return None

        df = pd.read_csv(file_path, dtype=str)

        rename_map = {'Pincode': 'PINCode', 'StateName': 'State'}
        df.rename(columns=rename_map, inplace=True)

        # Define source columns for SearchableText (order might matter for emphasis later)
        search_text_source_columns = ['OfficeName', 'DivisionName', 'District', 'State'] # Added State

        for col in search_text_source_columns:
            if col not in df.columns:
                print(f"Warning: Source column '{col}' for SearchableText not found. Skipping.")
                df[col] = "" # Create empty if missing to prevent error

        # Create 'SearchableText'
        df['SearchableText'] = ""
        for col in search_text_source_columns:
            df[col] = df[col].fillna('').astype(str).str.lower() # Lowercase source before concat
            df['SearchableText'] += df[col] + " "
        
        df['SearchableText'] = df['SearchableText'].str.strip()
        # Optional: Remove specific stop words from the SearchableText data
        # df['SearchableText'] = df['SearchableText'].apply(lambda x: remove_data_stop_words(x, DATA_STOP_WORDS))


        # Preprocessing for other critical columns
        columns_to_lowercase_and_fill_na = {
            # 'OfficeName' is already handled and lowercased for SearchableText
            'OfficeType': str,
            'Delivery': str,
            # 'District', 'State' also already handled for SearchableText
        }
        for col, col_type in columns_to_lowercase_and_fill_na.items():
            if col in df.columns:
                df[col] = df[col].fillna('').astype(col_type).str.lower()
            else:
                print(f"Warning: Expected column '{col}' not found for processing.")
                df[col] = ""

        if 'PINCode' in df.columns:
            df['PINCode'] = df['PINCode'].fillna('').astype(str)
            df.dropna(subset=['PINCode'], inplace=True) # Drop if PIN is truly NaN
            df = df[df['PINCode'] != ''] # Drop if PIN is empty string
        else:
            print("Error: 'PINCode' column missing from the dataset.")
            return None
        
        # Create a normalized OfficeName for display (e.g., Title Case)
        # The original OfficeName (lower cased) is part of SearchableText
        if 'OfficeName' in df.columns:
             # df['OfficeName_normalized'] = df['OfficeName'].str.title() # Simple title case
             # Use original casing from CSV for 'OfficeName_for_display' if preferred, and use lowercased for matching
             df['OfficeName_for_display'] = df['OfficeName'] # Assume OfficeName from CSV has good casing
             df['OfficeName_lower'] = df['OfficeName'].str.lower() # For internal consistent matching key
        else:
            df['OfficeName_for_display'] = ""
            df['OfficeName_lower'] = ""


        print(f"Loaded {len(df)} records. Columns: {df.columns.tolist()}")
        return df

    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return None
    except Exception as e:
        print(f"An error occurred while loading the data: {e}")
        return None

if __name__ == '__main__':
    data = load_postal_data(file_path="../data/postal_data.csv")
    if data is not None:
        print("\nData loaded successfully (first 5 rows):")
        print(data[['PINCode', 'OfficeName_for_display', 'OfficeName_lower', 'DivisionName', 'District', 'State', 'Delivery', 'SearchableText']].head())
        print("\nInfo:")
        data.info()
