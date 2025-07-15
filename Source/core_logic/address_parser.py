import re

# More comprehensive list of common address suffixes and generic terms
# This list should be tailored to the Indian context
COMMON_ADDRESS_TERMS = {
    'road', 'rd', 'street', 'st', 'marg', 'path', 'lane', 'gali',
    'nagar', 'colony', 'layout', 'extension', 'extn',
    'sector', 'sec', 'phase', 'ph',
    'apartment', 'apartments', 'apt', 'appts',
    'building', 'bldg', 'complex',
    'house', 'no', 'number', 'num', 'hno',
    'near', 'opposite', 'opp', 'behind', 'beside', 'adj', 'adjacent',
    'main', 'cross',
    'area', 'zone', 'block', 'chowk', 'circle',
    'post', 'office', 'po', 'so', 'bo', 'ho', 'gpo', # Postal terms
    'tehsil', 'taluk', 'mandal', # Administrative terms
    'floor', 'flr', 'ground', 'grnd',
    'and', 'or', 'the', 'of', 'in', 'at', 'on', # Common English stop words
    'new', 'old', 'north', 'south', 'east', 'west', 'central' # Directions/modifiers sometimes noisy
}
# Add pincode itself as a stop word if found, as it's handled separately
# Numbers that are not pincodes (e.g., house numbers) can also be filtered if too short.

def parse_address(address_string):
    """
    Parses an address string to extract potential PIN code and locality keywords.
    Enhanced with a more comprehensive stop word list.
    """
    if not address_string or not isinstance(address_string, str):
        return {'pincode': None, 'locality_keywords': []}

    address_lower = address_string.lower()
    parsed_info = {'pincode': None, 'locality_keywords': []}

    # 1. Extract PIN code (6 digits)
    pin_match = re.search(r'\b(\d{6})\b', address_lower)
    if pin_match:
        parsed_info['pincode'] = pin_match.group(1)
        # Remove PIN from address string to get remaining parts for locality
        address_lower = re.sub(r'\b\d{6}\b', '', address_lower).strip()

    # 2. Extract locality keywords
    # Remove punctuation (except hyphens if they are part of names, e.g. "Anna-Nagar")
    address_cleaned = re.sub(r'[^\w\s-]', '', address_lower) # Keep words, spaces, hyphens
    
    # Split by common delimiters
    potential_keywords = re.split(r'[,\s\-/()]+', address_cleaned)
    
    keywords = []
    for kw_raw in potential_keywords:
        kw = kw_raw.strip()
        if not kw:
            continue
        
        # Filter out if it's a number (unless it's a significant number like a sector number)
        if kw.isdigit() and len(kw) < 2: # Filter out single digits, allow "1st", "2nd" if not digits
            continue
        # More robust: if kw.isdigit() and kw != parsed_info['pincode'] and len(kw) < 3: # e.g. sector 15
            
        if len(kw) > 2 and kw not in COMMON_ADDRESS_TERMS:
            keywords.append(kw)
    
    parsed_info['locality_keywords'] = list(set(keywords)) # Use set to remove duplicates

    return parsed_info

if __name__ == '__main__':
    test_addresses = [
        "Connaught Place, New Delhi 110001",
        "MG Road, Bangalore, Main Area",
        "Near City Mall, Park Street, Kolkata 700016, West Bengal",
        "123 Main St, Indiranagar Stage 2, 560038",
        "Fort Area Mumbai, Opp GPO",
        "Invalid PIN 12345",
        "Sector 15, Part II, Gurgaon",
        "H.No 45, 3rd Cross, Shanti Nagar Colony, Hyderabad 500028"
    ]
    print("--- Address Parser Tests ---")
    for addr in test_addresses:
        print(f"Input: \"{addr}\" -> Parsed: {parse_address(addr)}")

