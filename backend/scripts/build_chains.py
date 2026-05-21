"""Build app/data/chains.json from a structured, categorized chain list.

Why a script instead of a static JSON: the field-ops user will discover
new chains during outreach. Adding them here and re-running is easier
than hand-editing a 500-row JSON file.

Match modes:
    exact      Normalized name must equal the chain string. Default. Safe.
    substring  Normalized name starts with or contains the chain string as
               a whole word. Use for chains whose names always start with
               the brand (e.g. "Wells Fargo Bank of Charlotte" should hit
               "wells fargo").

Quality bar: missing a Starbucks costs the user a real lead and burns
goodwill at Starbucks corporate. We're conservative with substring rules
to keep false positives near zero.
"""

from __future__ import annotations

import json
from pathlib import Path

# Each tuple: (display_name, category, match_mode)
# Display name is what shows in the UI. The script normalizes it for matching.

CHAINS: list[tuple[str, str, str]] = []

# Brand names that overlap with common English words. These stay exact-match
# even when the category default is substring, because substring would
# false-positive on independents ("Subway Tile Co", "Sonic Tools", "Big Apple
# Bakery", "The Gap Insurance Agency"). False positives cost real leads, so
# we keep these conservative and miss the occasional appended-location form.
DANGEROUS_AS_SUBSTRING = {
    # Dictionary words / short brand names that overlap with real independents
    "Subway", "Sonic", "Sonic Drive-In", "Apple", "Apple Store",
    "Target", "Gap", "Crunch", "Lids", "PINK", "Element", "Aloft",
    "Tru", "Curves", "Discover", "Citizens", "Huntington", "Regions",
    "Marathon", "Sunoco", "Shell", "BP", "Mobil", "Schwab", "Jewel",
    # Two-letter or numeric brand codes never safe as substrings
    "76", "TA", "BP",
    # Specifically risky: "Bank of America" appears in independent names like
    # "First Bank of America's Hometown" - keep exact match.
    "Bank of America",
    # Coffee/food brands whose canonical names are common phrases
    "Boost Mobile",
}


def add(category: str, names: list[str], match_mode: str = "exact") -> None:
    """Append a batch of names under one category.

    If match_mode == "substring", we still keep dangerous-as-substring names
    on exact mode to avoid false positives. False positives (flagging an
    independent as a chain) cost the user a real lead; false negatives are
    recoverable by manual review.
    """
    for n in names:
        mode = match_mode
        if mode == "substring" and n in DANGEROUS_AS_SUBSTRING:
            mode = "exact"
        CHAINS.append((n, category, mode))


# ---------------------------------------------------------------------------
# Fast food + quick-service restaurants
# ---------------------------------------------------------------------------
add("qsr", [
    "McDonald's", "Burger King", "Wendy's", "Subway", "Starbucks",
    "Dunkin'", "Dunkin' Donuts", "Chick-fil-A", "Taco Bell", "KFC",
    "Pizza Hut", "Domino's", "Domino's Pizza", "Papa John's",
    "Papa Murphy's", "Little Caesars", "Chipotle",
    "Chipotle Mexican Grill", "Panera", "Panera Bread", "Five Guys",
    "Shake Shack", "In-N-Out", "In-N-Out Burger", "Whataburger",
    "Culver's", "Sonic", "Sonic Drive-In", "Arby's", "Hardee's",
    "Carl's Jr.", "Carl's Jr", "Del Taco", "Jack in the Box",
    "Popeyes", "Popeyes Louisiana Kitchen", "Bojangles",
    "Bojangles'", "Church's Chicken", "Raising Cane's",
    "Raising Cane's Chicken Fingers", "Zaxby's", "El Pollo Loco",
    "Wingstop", "Buffalo Wild Wings", "Jersey Mike's",
    "Jersey Mike's Subs", "Jimmy John's", "Firehouse Subs",
    "Quiznos", "Potbelly", "Potbelly Sandwich Shop",
    "Tropical Smoothie Cafe", "Smoothie King", "Jamba", "Jamba Juice",
    "Auntie Anne's", "Cinnabon", "Pretzelmaker", "Wetzel's Pretzels",
    "Krispy Kreme", "Tim Hortons", "Caribou Coffee", "Peet's Coffee",
    "Peet's Coffee & Tea", "Dutch Bros", "Dutch Bros Coffee",
    "Scooter's Coffee", "Ben & Jerry's", "Cold Stone Creamery",
    "Baskin-Robbins", "Dairy Queen", "Carvel", "TCBY", "Yogurtland",
    "Pinkberry", "Menchie's", "Sweetgreen", "Cava",
    "Honey Baked Ham", "Boston Market", "Long John Silver's",
    "Captain D's", "A&W", "A&W Restaurants", "Steak 'n Shake",
    "Krystal", "White Castle", "Checkers", "Rally's", "Cook Out",
    "Texas Roadhouse", "LongHorn Steakhouse", "Outback Steakhouse",
    "Logan's Roadhouse", "Chili's", "Chili's Grill & Bar",
    "Applebee's", "Applebee's Neighborhood Grill + Bar", "TGI Fridays",
    "T.G.I. Friday's", "Ruby Tuesday", "Cracker Barrel",
    "Cracker Barrel Old Country Store", "Olive Garden", "Red Lobster",
    "Bonefish Grill", "P.F. Chang's", "Pei Wei", "Panda Express",
    "Manchu Wok", "Sarku Japan", "Benihana", "The Cheesecake Factory",
    "Cheesecake Factory", "Maggiano's", "Maggiano's Little Italy",
    "Carrabba's", "Carrabba's Italian Grill", "Bahama Breeze",
    "Buca di Beppo", "Bertucci's", "Romano's Macaroni Grill",
    "On the Border", "On the Border Mexican Grill & Cantina",
    "Chevys", "Chevy's", "Saltgrass Steak House", "Texas de Brazil",
    "Fogo de Chao", "Fogo de Chão", "BJ's Restaurant",
    "BJ's Restaurant & Brewhouse", "Yard House", "Bar Louie",
    "World of Beer", "Hooters", "Twin Peaks", "Miller's Ale House",
    "Mellow Mushroom", "Marco's Pizza", "Rosati's", "Hungry Howie's",
    "Round Table Pizza", "CiCi's Pizza", "Pizza Inn", "MOD Pizza",
    "Pieology", "Blaze Pizza", "Mountain Mike's Pizza",
    "Donatos Pizza", "Cottage Inn", "Beef 'O' Brady's",
    "Caribou Coffee", "The Coffee Bean & Tea Leaf",
    "The Coffee Bean", "Pret A Manger", "Le Pain Quotidien",
    "Au Bon Pain", "Corner Bakery", "Corner Bakery Cafe",
    "Einstein Bagels", "Einstein Bros. Bagels", "Einstein Bros Bagels",
    "Bruegger's Bagels", "Bruegger's",
])

# ---------------------------------------------------------------------------
# Coffee giants with location naming patterns -> substring mode
# ---------------------------------------------------------------------------
add("qsr_substring", [
    "Starbucks Coffee", "Dunkin' Donuts Coffee",
], match_mode="substring")

# ---------------------------------------------------------------------------
# Grocery, big-box, warehouse
# ---------------------------------------------------------------------------
add("grocery_bigbox", match_mode="substring", names=[
    "Walmart", "Walmart Supercenter", "Walmart Neighborhood Market",
    "Sam's Club", "Target", "Costco", "Costco Wholesale",
    "Kroger", "Publix", "Publix Super Market",
    "Publix Super Markets", "Safeway", "Albertsons", "Whole Foods",
    "Whole Foods Market", "Trader Joe's", "Aldi", "Lidl",
    "Sprouts", "Sprouts Farmers Market", "Wegmans",
    "Giant", "Giant Eagle", "Giant Food", "Stop & Shop",
    "Food Lion", "Harris Teeter", "Winn-Dixie", "Piggly Wiggly",
    "IGA", "Save A Lot", "Save-A-Lot", "Hannaford",
    "Shaw's", "Shaw's Supermarket", "Acme", "Acme Markets",
    "Ralphs", "Vons", "Pavilions", "Smart & Final",
    "ShopRite", "Price Chopper", "Tops", "Tops Friendly Markets",
    "Meijer", "HEB", "H-E-B", "Heinen's", "Schnucks",
    "Hy-Vee", "Cub Foods", "Jewel-Osco", "Jewel",
    "Food 4 Less", "Smith's", "Smith's Food and Drug",
    "Fry's", "Fry's Food Stores", "King Soopers", "QFC",
    "Mariano's", "Pick 'n Save", "Food City", "Bashas'",
    "Stater Bros", "Stater Bros. Markets", "WinCo Foods",
    "Grocery Outlet", "Grocery Outlet Bargain Market",
])

# ---------------------------------------------------------------------------
# Convenience, gas stations, truck stops
# ---------------------------------------------------------------------------
add("gas_convenience", match_mode="substring", names=[
    "7-Eleven", "Circle K", "Wawa", "Sheetz", "QuikTrip", "QT",
    "Speedway", "Casey's", "Casey's General Store", "Royal Farms",
    "Cumberland Farms", "Kwik Trip", "Kwik Star",
    "Pilot Flying J", "Pilot", "Flying J", "Love's",
    "Love's Travel Stops", "Love's Travel Stop", "TravelCenters of America",
    "TA", "Stewart's", "Stewart's Shops", "Maverik",
    "Holiday Stationstores", "Allsup's", "Buc-ee's",
    "Stripes", "Sunoco", "Shell", "BP", "Exxon", "ExxonMobil",
    "Mobil", "Chevron", "Texaco", "Marathon", "Phillips 66",
    "Conoco", "Valero", "Citgo", "76", "Murphy USA",
    "Murphy Express", "ARCO", "Gulf", "Sinclair",
    "Cumberland Farms", "GetGo", "Thorntons", "RaceTrac",
    "RaceWay", "Pilot Travel Centers",
])

# ---------------------------------------------------------------------------
# Home improvement, hardware, building supply
# ---------------------------------------------------------------------------
add("home_improvement", match_mode="substring", names=[
    "The Home Depot", "Home Depot", "Lowe's", "Lowe's Home Improvement",
    "Ace Hardware", "True Value", "True Value Hardware",
    "Menards", "Harbor Freight", "Harbor Freight Tools",
    "Tractor Supply", "Tractor Supply Co.", "Tractor Supply Co",
    "Sherwin-Williams", "Benjamin Moore", "Floor & Decor",
    "Lumber Liquidators", "LL Flooring", "Sutherlands",
    "84 Lumber", "ABC Supply", "Builders FirstSource",
])

# ---------------------------------------------------------------------------
# Furniture, home goods, mattresses
# ---------------------------------------------------------------------------
add("furniture_home", [
    "IKEA", "Ashley HomeStore", "Ashley Furniture",
    "Ashley Furniture HomeStore", "Rooms To Go", "La-Z-Boy",
    "Bob's Discount Furniture", "Living Spaces", "Mattress Firm",
    "Sleep Number", "Mattress Warehouse", "Pottery Barn",
    "Pottery Barn Kids", "Crate & Barrel", "West Elm",
    "Restoration Hardware", "RH", "Williams Sonoma",
    "Williams-Sonoma", "HomeGoods", "At Home", "Big Lots",
    "Tuesday Morning", "World Market", "Cost Plus World Market",
    "Pier 1", "Pier 1 Imports", "Bed Bath & Beyond", "Buy Buy Baby",
    "The Container Store", "CB2", "Arhaus", "Havertys",
    "City Furniture", "El Dorado Furniture", "Value City Furniture",
    "American Freight", "American Signature Furniture",
    "Raymour & Flanigan", "Ethan Allen", "Sleep Outfitters",
    "Mattress Warehouse", "Sit 'n Sleep",
])

# ---------------------------------------------------------------------------
# Apparel, department stores, off-price
# ---------------------------------------------------------------------------
add("apparel_dept", match_mode="substring", names=[
    "Macy's", "Nordstrom", "Nordstrom Rack", "Dillard's",
    "JCPenney", "Kohl's", "Belk", "Burlington",
    "Burlington Coat Factory", "Ross", "Ross Dress for Less",
    "TJ Maxx", "T.J. Maxx", "Marshalls", "DSW",
    "Famous Footwear", "Foot Locker", "Champs Sports", "Finish Line",
    "Hibbett Sports", "Dick's Sporting Goods", "Academy Sports",
    "Academy Sports + Outdoors", "Bass Pro Shops", "Cabela's",
    "REI", "Big 5", "Big 5 Sporting Goods", "Old Navy", "Gap",
    "Banana Republic", "J.Crew", "J. Crew", "Madewell", "Athleta",
    "Anthropologie", "Urban Outfitters", "Free People", "Lululemon",
    "lululemon athletica", "H&M", "Forever 21", "Zara", "Uniqlo",
    "Hot Topic", "Spencer's", "Spencer Gifts", "Tilly's",
    "Lids", "Hat World", "Sunglass Hut", "LensCrafters",
    "Pearle Vision", "Visionworks", "America's Best",
    "America's Best Contacts & Eyeglasses", "MyEyeDr",
    "Stanton Optical", "Warby Parker", "Hallmark", "Carter's",
    "OshKosh B'gosh", "Children's Place", "The Children's Place",
    "Justice", "Gymboree", "DSW Designer Shoe Warehouse",
    "Shoe Carnival", "Rack Room Shoes", "Payless ShoeSource",
])

# ---------------------------------------------------------------------------
# Auto: repair, parts, dealers, rental, oil change, tires
# ---------------------------------------------------------------------------
add("auto_service", match_mode="substring", names=[
    "Jiffy Lube", "Valvoline Instant Oil Change", "Valvoline",
    "Midas", "Meineke", "Pep Boys", "AAMCO",
    "AAMCO Transmissions", "Big O Tires", "Discount Tire",
    "America's Tire", "Firestone", "Firestone Complete Auto Care",
    "Goodyear", "Goodyear Auto Service", "Mavis Tire",
    "Mavis Discount Tire", "NTB", "National Tire and Battery",
    "Tire Kingdom", "Tires Plus", "Christian Brothers Automotive",
    "Brakes Plus", "Brake Masters", "Brake Check", "Just Brakes",
    "Maaco", "Earl Scheib", "Ziebart", "Tuffy",
    "Tuffy Tire & Auto", "Monro", "Monro Muffler", "Car-X",
    "Express Oil Change", "Take 5 Oil Change", "Take 5",
    "AutoZone", "O'Reilly Auto Parts", "O'Reilly", "Advance Auto Parts",
    "NAPA Auto Parts", "NAPA",
    "CarMax", "Carvana", "AutoNation", "Sonic Automotive",
    "Group 1 Automotive", "Hertz", "Avis", "Enterprise",
    "Enterprise Rent-A-Car", "Budget", "Alamo", "National",
    "Thrifty", "Dollar", "Sixt", "Penske", "U-Haul",
    "Ryder", "Budget Truck",
])

# ---------------------------------------------------------------------------
# Self-storage
# ---------------------------------------------------------------------------
add("storage", match_mode="substring", names=[
    "Public Storage", "Extra Space Storage", "U-Haul Self-Storage",
    "Life Storage", "CubeSmart", "Cube Smart", "Storage King USA",
    "Simply Self Storage", "A-1 Self Storage", "Storage West",
    "StorageMart", "ezStorage", "iStorage", "Devon Self Storage",
    "Sentry Self Storage", "Metro Self Storage",
])

# ---------------------------------------------------------------------------
# Fitness / gyms
# ---------------------------------------------------------------------------
add("fitness", match_mode="substring", names=[
    "Planet Fitness", "LA Fitness", "Anytime Fitness",
    "24 Hour Fitness", "Equinox", "Crunch Fitness", "Crunch",
    "Gold's Gym", "Snap Fitness", "Orangetheory Fitness",
    "Orangetheory", "F45", "F45 Training", "Pure Barre",
    "SoulCycle", "CycleBar", "Title Boxing Club", "Title Boxing",
    "Burn Boot Camp", "9Round", "YMCA", "YWCA", "Curves",
    "Workout Anytime", "Retro Fitness", "Blink Fitness",
    "EOS Fitness", "Life Time", "Lifetime Fitness", "In-Shape",
    "Powerhouse Gym", "World Gym", "Fitness 19", "Youfit",
    "Youfit Health Clubs", "Club Pilates", "StretchLab",
    "Solidcore", "Barry's", "Barry's Bootcamp", "Row House",
    "FlyWheel",
])

# ---------------------------------------------------------------------------
# Pharmacy, beauty, personal care
# ---------------------------------------------------------------------------
add("pharmacy_beauty", match_mode="substring", names=[
    "CVS", "CVS Pharmacy", "Walgreens", "Rite Aid", "Duane Reade",
    "Sephora", "Ulta", "Ulta Beauty", "Bath & Body Works",
    "Victoria's Secret", "PINK", "Sally Beauty",
    "Sally Beauty Supply", "Massage Envy", "Hand & Stone",
    "European Wax Center", "Drybar", "Great Clips", "Supercuts",
    "Cost Cutters", "Sport Clips", "Fantastic Sams",
    "Hair Cuttery", "MasterCuts", "SmartStyle", "Sola Salon Studios",
])

# ---------------------------------------------------------------------------
# Telecom, electronics, banks, insurance
# ---------------------------------------------------------------------------
add("telecom_electronics", match_mode="substring", names=[
    "AT&T", "T-Mobile", "Verizon", "Verizon Wireless",
    "Sprint", "Cricket Wireless", "Cricket", "Boost Mobile",
    "Metro by T-Mobile", "MetroPCS", "Best Buy", "Apple Store",
    "Apple", "GameStop", "Microsoft Store", "Xfinity",
    "Xfinity Store", "Spectrum", "Spectrum Mobile",
])
add("banks_insurance", match_mode="substring", names=[
    "Bank of America", "Chase", "JPMorgan Chase", "Wells Fargo",
    "Citibank", "U.S. Bank", "PNC", "PNC Bank", "TD Bank",
    "Capital One", "Capital One Bank", "KeyBank", "Regions Bank",
    "Regions", "BB&T", "Truist", "Truist Bank", "M&T Bank",
    "BMO", "BMO Harris", "Fifth Third Bank", "Fifth Third",
    "Citizens Bank", "Citizens", "Huntington Bank", "Huntington",
    "HSBC", "Santander", "Santander Bank", "Ally Bank",
    "USAA", "Discover", "Discover Bank", "Charles Schwab",
    "Schwab", "Edward Jones", "Fidelity", "Northwestern Mutual",
    "Allstate", "State Farm", "Geico", "Progressive",
    "Farmers Insurance", "Farmers", "Liberty Mutual", "Nationwide",
    "American Family Insurance", "H&R Block", "Jackson Hewitt",
    "Liberty Tax", "Liberty Tax Service",
])

# ---------------------------------------------------------------------------
# Shipping, postal, office
# ---------------------------------------------------------------------------
add("shipping_office", match_mode="substring", names=[
    "The UPS Store", "UPS Store", "FedEx Office", "FedEx",
    "USPS", "Postal Annex", "Pak Mail", "Office Depot",
    "OfficeMax", "Office Depot OfficeMax", "Staples",
])

# ---------------------------------------------------------------------------
# Dollar stores, discount, hobby
# ---------------------------------------------------------------------------
add("discount_hobby", [
    "Dollar Tree", "Dollar General", "Family Dollar", "Five Below",
    "99 Cents Only", "Ollie's", "Ollie's Bargain Outlet",
    "Books-A-Million", "Barnes & Noble", "Half Price Books",
    "Michaels", "Hobby Lobby", "Jo-Ann", "Joann",
    "Jo-Ann Fabric", "Jo-Ann Fabrics", "Party City",
    "Spirit Halloween", "PetSmart", "Petco", "Pet Supplies Plus",
])

# ---------------------------------------------------------------------------
# Hotels (flat-roof common but corporate procurement = chain).
# ALWAYS substring mode: hotel names append the city or airport code.
# ---------------------------------------------------------------------------
add("hotels", match_mode="substring", names=[
    "Holiday Inn", "Holiday Inn Express", "Hampton Inn",
    "Hampton Inn & Suites", "Hilton", "Hilton Garden Inn",
    "DoubleTree", "Embassy Suites", "Marriott", "Courtyard",
    "Courtyard by Marriott", "Residence Inn", "Fairfield Inn",
    "Fairfield Inn & Suites", "SpringHill Suites", "TownePlace Suites",
    "Renaissance", "Sheraton", "Westin", "Hyatt", "Hyatt Place",
    "Hyatt House", "InterContinental", "Crowne Plaza",
    "Staybridge Suites", "Candlewood Suites", "Best Western",
    "Best Western Plus", "La Quinta", "La Quinta Inn",
    "Quality Inn", "Comfort Inn", "Comfort Suites", "Sleep Inn",
    "MainStay Suites", "Clarion", "Econo Lodge", "Days Inn",
    "Super 8", "Travelodge", "Microtel", "Wyndham",
    "Howard Johnson", "Ramada", "Baymont", "Wingate",
    "Tru", "Country Inn & Suites", "Red Roof Inn", "Red Roof",
    "Motel 6", "Studio 6", "Extended Stay America",
    "WoodSpring Suites", "Aloft", "Element", "Home2 Suites",
    "Home2",
])

# ---------------------------------------------------------------------------
# Substring rules for parent brands whose locations vary widely
# ---------------------------------------------------------------------------
add("substring_brands", [
    "Wells Fargo", "Bank of America",
], match_mode="substring")


def main() -> None:
    """Write app/data/chains.json."""
    out_dir = Path(__file__).resolve().parent.parent / "app" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Dedupe while preserving order (display string is the key).
    seen = set()
    chains_out = []
    for name, category, mode in CHAINS:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        chains_out.append({"name": name, "category": category, "match_mode": mode})

    payload = {
        "version": 1,
        "count": len(chains_out),
        "chains": chains_out,
    }
    out_path = out_dir / "chains.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(chains_out)} chains to {out_path}")


if __name__ == "__main__":
    main()
