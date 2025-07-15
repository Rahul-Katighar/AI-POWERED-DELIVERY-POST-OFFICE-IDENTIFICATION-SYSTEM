import pandas as pd
from collections import Counter
from fuzzywuzzy import fuzz # For fuzzy matching

# Define weights for matches in different fields
FIELD_WEIGHTS = {
    'OfficeName_lower': 1.0,   # Highest weight for direct match in office name
    'DivisionName': 0.7,
    'District': 0.5,
    'State': 0.2,         # Lower weight for state, usually too broad
    # 'SearchableText' direct match can be a fallback or combined score
}
FUZZY_MATCH_THRESHOLD = 80 # Score out of 100 for fuzzywuzzy (e.g., 80 means 80% similar)

def calculate_match_score(row, locality_keywords):
    """
    Calculates a score for a row based on how many keywords match
    in different fields, considering weights and fuzzy matching.
    """
    score = 0
    matched_keywords_details = {} # To store which keyword matched which field

    # Use the pre-lower-cased versions from data_loader
    office_name_text = row.get('OfficeName_lower', "")
    division_name_text = row.get('DivisionName', "") # Assumed lowercased by data_loader
    district_text = row.get('District', "")       # Assumed lowercased by data_loader
    state_text = row.get('State', "")             # Assumed lowercased by data_loader
    searchable_text_full = row.get('SearchableText', "") # Already lowercased

    present_keywords = set()

    for keyword in locality_keywords:
        keyword_matched_in_iteration = False
        # Exact match in OfficeName (highest priority)
        if keyword in office_name_text:
            score += FIELD_WEIGHTS['OfficeName_lower']
            matched_keywords_details[keyword] = 'OfficeName'
            present_keywords.add(keyword)
            keyword_matched_in_iteration = True
            continue # Prioritize this match for the keyword

        # Exact match in DivisionName
        if keyword in division_name_text:
            score += FIELD_WEIGHTS['DivisionName']
            matched_keywords_details[keyword] = 'DivisionName'
            present_keywords.add(keyword)
            keyword_matched_in_iteration = True
            continue

        # Exact match in District
        if keyword in district_text:
            score += FIELD_WEIGHTS['District']
            matched_keywords_details[keyword] = 'District'
            present_keywords.add(keyword)
            keyword_matched_in_iteration = True
            continue
        
        # Exact match in State (less impactful but can help disambiguate)
        if keyword in state_text:
            score += FIELD_WEIGHTS['State']
            matched_keywords_details[keyword] = 'State'
            present_keywords.add(keyword)
            keyword_matched_in_iteration = True
            continue

        # --- Fuzzy Matching as a fallback for this keyword ---
        # Fuzzy match in OfficeName
        if fuzz.partial_ratio(keyword, office_name_text) >= FUZZY_MATCH_THRESHOLD:
            score += FIELD_WEIGHTS['OfficeName_lower'] * 0.8 # Penalize fuzzy slightly
            matched_keywords_details[keyword] = 'OfficeName (Fuzzy)'
            present_keywords.add(keyword)
            keyword_matched_in_iteration = True
            continue

        # Fuzzy match in DivisionName
        if fuzz.partial_ratio(keyword, division_name_text) >= FUZZY_MATCH_THRESHOLD:
            score += FIELD_WEIGHTS['DivisionName'] * 0.8
            matched_keywords_details[keyword] = 'DivisionName (Fuzzy)'
            present_keywords.add(keyword)
            keyword_matched_in_iteration = True
            continue
        
        # Fuzzy match in District
        if fuzz.partial_ratio(keyword, district_text) >= FUZZY_MATCH_THRESHOLD:
            score += FIELD_WEIGHTS['District'] * 0.8
            matched_keywords_details[keyword] = 'District (Fuzzy)'
            present_keywords.add(keyword)
            keyword_matched_in_iteration = True
            continue

        # As a last resort for keyword, check general SearchableText (exact only for this part)
        if not keyword_matched_in_iteration and keyword in searchable_text_full:
            score += 0.1 # Small bonus if found in general text but not specific fields
            matched_keywords_details[keyword] = 'Other Details'
            present_keywords.add(keyword)


    # Bonus for multiple unique keywords matched
    if len(present_keywords) > 1:
        score += len(present_keywords) * 0.2 

    return score, matched_keywords_details


def find_dpo_and_pin(parsed_address, postal_df):
    if postal_df is None or postal_df.empty:
        return {'status': 'error', 'message': 'Postal data is not loaded or empty.'}

    input_pin = parsed_address.get('pincode')
    locality_keywords = parsed_address.get('locality_keywords', [])

    # Ensure necessary columns are present (created by data_loader)
    required_cols = ['PINCode', 'OfficeName_for_display', 'OfficeName_lower', 'DivisionName', 'District', 'State', 'Delivery', 'SearchableText']
    for col in required_cols:
        if col not in postal_df.columns:
            return {'status': 'error', 'message': f"Required column '{col}' not found in postal data. Check data_loader."}

    results = []

    # --- Strategy 1: If PIN is provided ---
    if input_pin:
        pin_matches_df = postal_df[postal_df['PINCode'] == input_pin].copy() # Use .copy() to avoid SettingWithCopyWarning
        if not pin_matches_df.empty:
            # Filter for DPOs
            dpos_in_pin = pin_matches_df[pin_matches_df['Delivery'] == 'delivery']

            if not dpos_in_pin.empty:
                if not locality_keywords: # PIN match, DPOs exist, no locality given
                    best_dpo_for_pin = dpos_in_pin.iloc[0]
                    return {
                        'status': 'success_pin_only_dpo',
                        'pin': best_dpo_for_pin['PINCode'],
                        'dpo': best_dpo_for_pin['OfficeName_for_display'], # Use display name
                        'message': f"Found DPO for PIN {input_pin}. Locality not specified."
                    }
                else: # PIN match, DPOs exist, locality keywords given
                    # Score DPOs within this PIN based on locality keywords
                    pin_matches_df['match_score'], pin_matches_df['matched_details'] = zip(
                        *pin_matches_df.apply(lambda row: calculate_match_score(row, locality_keywords), axis=1)
                    )
                    
                    # Filter for actual DPOs and sort by score
                    scored_dpos = pin_matches_df[pin_matches_df['Delivery'] == 'delivery'].sort_values(by='match_score', ascending=False)
                    
                    if not scored_dpos.empty and scored_dpos.iloc[0]['match_score'] > 0:
                        best_match_row = scored_dpos.iloc[0]
                        matched_kws_str = ", ".join(f"'{k}' ({v})" for k,v in best_match_row['matched_details'].items())
                        return {
                            'status': 'success',
                            'pin': best_match_row['PINCode'],
                            'dpo': best_match_row['OfficeName_for_display'],
                            'score': round(best_match_row['match_score'], 2),
                            'message': f"Match found for PIN {input_pin}. Keywords matched: {matched_kws_str}."
                        }
                    else: # PIN DPOs exist, but locality keywords didn't match well
                        fallback_dpo = dpos_in_pin.iloc[0]
                        return {
                            'status': 'partial_match_pin',
                            'pin': fallback_dpo['PINCode'],
                            'dpo': fallback_dpo['OfficeName_for_display'],
                            'message': f"PIN {input_pin} has DPOs, but locality keywords didn't strongly match. Suggested first DPO."
                        }
            else: # PIN is valid, but no office marked 'delivery'
                first_office_in_pin = pin_matches_df.iloc[0]
                return {
                    'status': 'partial_match_pin_no_dpo_flag',
                    'pin': first_office_in_pin['PINCode'],
                    'dpo': first_office_in_pin['OfficeName_for_display'],
                    'message': f"PIN {input_pin} is valid, but no office explicitly marked as 'Delivery'. Suggested first office in PIN."
                }
        # else: input_pin was not found in data, fall through to locality-only search
        pass


    # --- Strategy 2: No valid PIN match, search by locality across all data ---
    if not locality_keywords: # Should only happen if PIN was also not given
        return {'status': 'not_found', 'message': 'Insufficient information: No PIN or locality keywords provided.'}

    # Calculate scores for all rows in the dataset
    # This can be slow on very large datasets. Consider pre-filtering or indexing for production.
    postal_df_copy = postal_df.copy()
    postal_df_copy['match_score'], postal_df_copy['matched_details'] = zip(
        *postal_df_copy.apply(lambda row: calculate_match_score(row, locality_keywords), axis=1)
    )
    
    # Filter for rows with a positive match score and sort
    # Prioritize 'Delivery' offices
    potential_matches = postal_df_copy[postal_df_copy['match_score'] > 0].copy()
    if potential_matches.empty:
        return {'status': 'not_found', 'message': 'Could not determine DPO/PIN based on locality keywords.'}

    # Sort by DPO status (delivery first), then by score
    potential_matches['is_dpo'] = (potential_matches['Delivery'] == 'delivery').astype(int)
    sorted_matches = potential_matches.sort_values(by=['is_dpo', 'match_score'], ascending=[False, False])

    if not sorted_matches.empty:
        best_match_row = sorted_matches.iloc[0]
        matched_kws_str = ", ".join(f"'{k}' ({v})" for k,v in best_match_row['matched_details'].items())
        status_suffix = " (DPO)" if best_match_row['is_dpo'] else " (Non-DPO)"
        
        return {
            'status': f'success_locality{status_suffix}',
            'pin': best_match_row['PINCode'],
            'dpo': best_match_row['OfficeName_for_display'],
            'score': round(best_match_row['match_score'], 2),
            'message': f"Match found by locality. Keywords matched: {matched_kws_str}."
        }

    return {'status': 'not_found', 'message': 'Could not determine DPO/PIN based on provided locality keywords after scoring.'}


if __name__ == '__main__':
    # Simulate data loaded by data_loader.py
    sample_data_list = [
        # PIN, OfficeName, DivisionName, District, State, OfficeType, Delivery
        ('515631', 'Peddakotla B.O', 'Hindupur Division', 'ANANTAPUR', 'ANDHRA PRADESH', 'BO', 'Delivery'),
        ('560038', 'Indiranagar S.O', 'Bangalore East Division', 'Bangalore Urban', 'KARNATAKA', 'SO', 'Delivery'),
        ('560001', 'Bangalore GPO', 'Bangalore GPO Division', 'Bangalore Urban', 'KARNATAKA', 'GPO', 'Delivery'),
        ('110001', 'Connaught Place H.O', 'New Delhi Central Division', 'New Delhi', 'DELHI', 'HO', 'Delivery'),
        ('110001', 'Parliament Street H.O', 'New Delhi Central Division', 'New Delhi', 'DELHI', 'HO', 'Non-Delivery'),
        ('751001', 'Bhubaneswar GPO', 'Bhubaneswar Division', 'KHURDA', 'ODISHA', 'GPO', 'Delivery'),
        ('751003', 'Kharabela Nagar S.O', 'Bhubaneswar Division', 'KHURDA', 'ODISHA', 'SO', 'Delivery'),
        ('400001', 'Mumbai GPO', 'Mumbai GPO Division', 'Mumbai', 'MAHARASHTRA', 'GPO', 'Delivery'),
    ]
    test_df = pd.DataFrame(sample_data_list, columns=['PINCode', 'OfficeName', 'DivisionName', 'District', 'State', 'OfficeType', 'Delivery'])

    # --- Simulate data_loader transformations ---
    test_df['OfficeName_for_display'] = test_df['OfficeName'] # Assuming original casing is fine for display
    for col in ['OfficeName', 'DivisionName', 'District', 'State', 'Delivery', 'OfficeType']:
        test_df[col] = test_df[col].str.lower()
    test_df.rename(columns={'OfficeName': 'OfficeName_lower'}, inplace=True) # Rename for clarity

    search_text_cols = ['OfficeName_lower', 'DivisionName', 'District', 'State']
    test_df['SearchableText'] = ""
    for col_st in search_text_cols:
        test_df['SearchableText'] += test_df[col_st].fillna('').astype(str) + " "
    test_df['SearchableText'] = test_df['SearchableText'].str.strip()
    # --- End of data_loader simulation ---

    print("\n--- Test Cases for matching_engine (with Scoring & Fuzzy Matching) ---")

    def run_test(description, address_str):
        print(f"\n--- {description} ---")
        print(f"Address: \"{address_str}\"")
        parsed = parse_address(address_str)
        print(f"Parsed: {parsed}")
        if test_df is not None and not test_df.empty:
            result = find_dpo_and_pin(parsed, test_df)
            print(f"Result: {result}")
        else:
            print("Test DF is empty or None.")

    run_test("PIN & Exact Locality (OfficeName)", "Connaught Place, New Delhi 110001")
    run_test("PIN & Fuzzy Locality (OfficeName)", "Conaught Plaace, New Delhi 110001") # Typo
    run_test("PIN & Locality (DivisionName)", "New Delhi Central 110001")
    run_test("Locality Only (OfficeName)", "Indiranagar, Bangalore")
    run_test("Locality Only (Fuzzy OfficeName)", "Indranagar, Banglore") # Typos
    run_test("Locality Only (District & State)", "Khurda Odisha")
    run_test("Locality Only (Multiple Keywords, Higher Score)", "Kharabela Nagar Bhubaneswar")
    run_test("PIN ok, Locality mismatch", "Random Street 110001")
    run_test("PIN & Locality (Non-DPO Office)", "Parliament Street 110001")
    run_test("No PIN, Ambiguous Locality (e.g. 'Mumbai')", "Mumbai")
    run_test("Specific Locality, No PIN", "Peddakotla")
    run_test("Insufficient Info", "   ")
    run_test("Only PIN, no locality", "560038")
