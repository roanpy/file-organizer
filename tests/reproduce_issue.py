import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from software_organizer.file_ops import find_target_matches


def test_location_preserved():
    # Mock source file
    source_file = {
        "name": "TestApp",
        "extension": ".dmg",
        "category": "test_cat",
        "version": "2.0",
    }

    # Mock target software list (Pre-enriched as server.py does)
    target_software = [
        {
            "name": "TestApp",
            "extension": ".dmg",
            "category": "test_cat",
            "version": "1.0",
            "path": "/target/TestApp.dmg",
            "location": "target",  # <--- CRITICAL PROPERTY
            "is_kept": False,
        },
        {
            "name": "OtherApp",
            "extension": ".dmg",
            "category": "test_cat",
            "location": "target",
        },
    ]

    print("--- Testing find_target_matches with pre-enriched list ---")

    # Call the function
    matches = find_target_matches(source_file, target_software)

    if not matches:
        print("FAIL: No matches found.")
        return

    first_match = matches[0]
    print(f"Match found: {first_match['name']}")

    # Check if 'location' property is preserved
    if "location" in first_match:
        print(f"SUCCESS: 'location' property found: {first_match['location']}")
        if first_match["location"] == "target":
            print("PASS: Location is correct.")
        else:
            print(f"FAIL: Location value is {first_match['location']}")
    else:
        print("FAIL: 'location' property MISSING in match result!")
        print("Keys found:", first_match.keys())


if __name__ == "__main__":
    test_location_preserved()
