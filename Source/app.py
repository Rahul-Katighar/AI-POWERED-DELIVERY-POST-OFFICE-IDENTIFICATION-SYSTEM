from core_logic.data_loader import load_postal_data
from core_logic.address_parser import parse_address
from core_logic.matching_engine import find_dpo_and_pin

def main_cli():
    """
    Main function for the Command Line Interface.
    """
    print("Welcome to the AI-Powered Delivery Post Office Identification System!")
    print("Loading postal data...")
    
    # Path relative to this app.py file (which is in the project root)
    postal_data_df = load_postal_data(file_path="data/postal_data.csv")

    if postal_data_df is None:
        print("Failed to load postal data. Exiting.")
        return

    print("Postal data loaded successfully.")
    print("-" * 30)

    while True:
        address_input = input("Enter address (or type 'exit' to quit): ").strip()
        if address_input.lower() == 'exit':
            break
        if not address_input:
            print("Please enter an address.")
            continue

        print(f"\nProcessing address: '{address_input}'")
        
        parsed_components = parse_address(address_input)
        print(f"Parsed components: {parsed_components}")
        
        suggestion = find_dpo_and_pin(parsed_components, postal_data_df)
        
        print("\n--- Suggestion ---")
        if suggestion['status'].startswith('success'):
            print(f"  Status:  SUCCESS")
            print(f"  PIN Code: {suggestion.get('pin', 'N/A')}")
            print(f"  Delivery Post Office (DPO): {suggestion.get('dpo', 'N/A')}")
            print(f"  Message: {suggestion.get('message', '')}")
        elif suggestion['status'] == 'partial_match_pin':
            print(f"  Status: PARTIAL MATCH (PIN based)")
            print(f"  Input PIN: {parsed_components.get('pincode')}")
            print(f"  Suggested PIN Code: {suggestion.get('pin', 'N/A')}")
            print(f"  Suggested Delivery Post Office (DPO): {suggestion.get('dpo', 'N/A')}")
            print(f"  Message: {suggestion.get('message', '')}")
        elif suggestion['status'] == 'not_found':
            print(f"  Status:  NOT FOUND")
            print(f"  Message: {suggestion.get('message', '')}")
        else: # error or other statuses
            print(f"  Status:  {suggestion['status'].upper()}")
            print(f"  Message: {suggestion.get('message', '')}")
        
        print("---------------------\n")

    print("Thank you for using the system. Goodbye!")

if __name__ == "__main__":
    main_cli()