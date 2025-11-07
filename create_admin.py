# scripts/seed_all_teams.py

from db import SessionLocal
from models import Team
from sqlalchemy import select

# ---------------------------------------------------
# Your full logo_map (paste exactly what you sent)
# ---------------------------------------------------
logo_map = {
    "Air Force": "Air_Force_Falcons_logo-300x300.png",
    "Akron": "Akron_Zips_logo-300x300.png",
    "UAB": "Alabama-Birmingham-Blazers-logo-300x300.png",
    "Alabama": "Alabama_Crimson_Tide_logo-300x300.png",
    "Appalachian State": "Appalachian_State_Mountaineers_logo-300x300.png",
    "Arizona State": "Arizona_State_Sun_Devils_logo-300x300.png",
    "Arizona": "Arizona_Wildcats_logo-300x300.png",
    "Arkansas State": "Arkansas_State_Red_Wolves_logo-300x300.png",
    "Arkansas": "Arkansas_Razorbacks_logo-300x300.png",
    "Army": "Army_West_Point_Black_Knights_logo-300x300.png",
    "Auburn": "Auburn_Tigers_logo-300x300.png",
    "Ball State": "Ball_State_Cardinals_logo-300x300.png",
    "Baylor": "Baylor_Bears_logo-300x300.png",
    "Boise State": "Boise_State_Broncos_Logo-300x300.png",
    "Boston College": "Boston_College_Eagles_logo-300x300.png",
    "Bowling Green": "Bowling_Green_Falcons_logo-300x300.png",
    "Buffalo": "Buffalo_Bulls_logo-300x300.png",
    "BYU": "BYU_Cougars_logo-300x300.png",
    "California": "California_Golden_Bears_logo-300x300.png",
    "Central Michigan": "Central_Michigan_Chippewas_logo-300x300.png",
    "Charlotte": "Charlotte_49ers_logo-300x300.png",
    "Cincinnati": "Cincinnati_Bearcats_logo-300x300.png",
    "Clemson": "Clemson_Tigers_logo-300x300.png",
    "Coastal Carolina": "Coastal_Carolina_Chanticleers_logo-300x300.png",
    "Colorado": "Colorado_Buffaloes_logo-300x300.png",
    "Colorado State": "Colorado_State_Rams_logo-300x300.png",
    "UConn": "Connecticut_Huskies_logo-300x300.png",
    "Duke": "Duke_Blue_Devils_logo-300x300.png",
    "East Carolina": "East_Carolina_Pirates_logo-300x300.png",
    "Eastern Michigan": "Eastern_Michigan_Eagles_logo-300x300.png",
    "FIU": "FIU-Panthers-Logo-300x300.png",
    "Florida Atlantic": "Florida_Atlantic_Owls_logo-300x300.png",
    "Florida": "Florida_Gators_logo-300x300.png",
    "Florida State": "Florida_State_Seminoles_logo-300x300.png",
    "Fresno State": "Fresno_State_Bulldogs_logo-300x300.png",
    "Georgia Southern": "Georgia_Southern_Eagles_logo-300x300.png",
    "Georgia State": "Georgia_State_Panthers_logo-300x300.png",
    "Georgia Tech": "Georgia_Tech_Yellow_Jackets_logo-300x300.png",
    "Georgia": "Georgia_Bulldogs_logo-300x300.png",
    "Hawai‘i": "Hawaii_Rainbow_Warriors_logo-300x300.png",
    "Houston": "Houston_Cougars_logo-300x300.png",
    "Illinois": "Illinois_Fighting_Illini_logo-300x300.png",
    "Indiana": "Indiana_Hoosiers_logo-300x300.png",
    "Iowa State": "Iowa_State_Cyclones_logo-300x300.png",
    "Iowa": "Iowa_Hawkeyes_logo-300x300.png",
    "Jacksonville State": "Jacksonville-State-Gamecocks-logo-300x300.png",
    "James Madison": "James_Madison_Dukes_logo-300x300.png",
    "Kansas State": "Kansas_State_Wildcats_logo-300x300.png",
    "Kansas": "Kansas_Jayhawks_logo-300x300.png",
    "Kennesaw State": "Kennesaw-State-Owls-logo-300x300.png",
    "Kent State": "Kent_State_Golden_Flashes-300x300.png",
    "Kentucky": "Kentucky_Wildcats_logo-300x300.png",
    "Liberty": "Liberty_Flames_logo-300x300.png",
    "Louisiana": "Louisiana-Lafayette_Ragin_Cajuns_logo-300x300.png",
    "ULM": "Louisiana-Monroe_Warhawks_logo-300x300.png",
    "Louisiana Tech": "Louisiana_Tech_Bulldogs_logo-300x300.png",
    "Louisville": "Louisville_Cardinals_logo-300x300.png",
    "LSU": "LSU_Tigers-300x300.png",
    "Marshall": "Marshall_Thundering_Herd_logo-300x300.png",
    "Maryland": "Maryland_Terrapins_logo-300x300.png",
    "Memphis": "Memphis_Tigers_logo-300x300.png",
    "Miami (FL)": "Miami_Hurricanes_logo-300x300.png",
    "Miami (OH)": "Miami_OH_Redhawks_logo-300x300.png",
    "Michigan State": "Michigan_State_Spartans_logo-300x300.png",
    "Michigan": "Michigan_Wolverines_logo-300x300.png",
    "Middle Tennessee": "Middle-Tennessee-Blue-Raiders-logo-300x300.png",
    "Minnesota": "Minnesota_Golden_Gophers_logo-300x300.png",
    "Mississippi State": "Mississippi_State_Bulldogs_logo-300x300.png",
    "Missouri": "Missouri_Tigers_logo-300x300.png",
    "Navy": "Navy_Midshipmen_logo-300x300.png",
    "Nebraska": "Nebraska_Cornhuskers_logo-300x300.png",
    "Nevada": "Nevada_Wolf_Pack_logo-300x300.png",
    "New Mexico State": "New_Mexico_State_Aggies_logo-300x300.png",
    "New Mexico": "New_Mexico_Lobos_logo-300x300.png",
    "Northern Illinois": "Northern_Illinois_Huskies-300x300.png",
    "Northwestern": "Northwestern_Wildcats_logo-300x300.png",
    "North Carolina": "North_Carolina_Tar_Heels_logo-300x300.png",
    "NC State": "North_Carolina_State_Wolfpack_logo-300x300.png",
    "North Texas": "North_Texas_Mean_Green_logo-300x300.png",
    "Notre Dame": "Notre_Dame_Fighting_Irish_logo-300x300.png",
    "Ohio": "Ohio_Bobcats_logo-300x300.png",
    "Ohio State": "Ohio_State_Buckeyes_logo-300x300.png",
    "Oklahoma State": "Oklahoma_State_Cowboys_logo-300x300.png",
    "Oklahoma": "Oklahoma_Sooners_logo-300x300.png",
    "Old Dominion": "Old_Dominion_Monarchs_logo-300x300.png",
    "Ole Miss": "Ole_Miss_Rebels_logo-300x300.png",
    "Oregon State": "Oregon_State_Beavers_logo-300x300.png",
    "Oregon": "Oregon_Ducks_logo-300x300.png",
    "Penn State": "Penn_State_Nittany_Lions_logo-300x300.png",
    "Pitt": "Pitt_Panthers_logo-300x300.png",
    "Purdue": "Purdue_Boilermakers_logo-300x300.png",
    "Rice": "Rice_Owls_logo-300x300.png",
    "Rutgers": "Rutgers_Scarlet_Knights_logo-300x300.png",
    "Sam Houston": "Sam-Houston-State-Bearkats-logo-300x300.png",
    "San Diego State": "San_Diego_State_Aztecs_logo-300x300.png",
    "San José State": "San_Jose_State_Spartans_logo-300x300.png",
    "SMU": "SMU_Mustang_logo-300x300.png",
    "Southern Miss": "Southern_Miss_Golden_Eagles_logo-300x300.png",
    "South Alabama": "South_Alabama_Jaguars_logo-300x300.png",
    "South Carolina": "South_Carolina_Gamecocks_logo-300x300.png",
    "South Florida": "South_Florida_Bulls_logo-300x300.png",
    "Stanford": "Stanford_Cardinal_logo-300x300.png",
    "Syracuse": "Syracuse_Orange_logo-300x300.png",
    "TCU": "TCU_Horned_Frogs_logo-300x300.png",
    "Temple": "Temple_Owls_logo-300x300.png",
    "Tennessee": "Tennessee_Volunteers_logo-300x300.png",
    "UTSA": "Texas-SA-Roadrunners-logo-300x300.png",
    "Texas A&M": "Texas_AM_University_logo-300x300.png",
    "Texas": "Texas_Longhorns_logo-300x300.png",
    "Texas State": "Texas_State_Bobcats_logo-300x300.png",
    "Texas Tech": "Texas_Tech_Red_Raiders_logo-300x300.png",
    "Toledo": "Toledo_Rockets_logo-300x300.png",
    "Troy": "Troy_Trojans_logo-300x300.png",
    "Tulane": "Tulane_Green_Wave_logo-300x300.png",
    "Tulsa": "Tulsa_Golden_Hurricane_logo-300x300.png",
    "UCF": "UCF_Knights_logo-300x300.png",
    "UCLA": "UCLA_Bruins-300x300.png",
    "UMass": "UMass_Amherst_Minutemen_logo-300x300.png",
    "UNLV": "UNLV_Rebels_logo-300x300.png",
    "USC": "USC_Trojans_logo-300x300.png",
    "UTEP": "UTEP-Miners-logo-300x300.png",
    "Utah State": "Utah_State_Aggies_logo-300x300.png",
    "Utah": "Utah_Utes_logo-300x300.png",
    "Vanderbilt": "Vanderbilt_Commodores_logo-300x300.png",
    "Virginia Tech": "Virginia_Tech_Hokies_logo-300x300.png",
    "Virginia": "Virginia_Cavaliers_logo-300x300.png",
    "Wake Forest": "Wake_Forest_Demon_Deacons_logo-300x300.png",
    "Washington State": "Washington_State_Cougars_logo-300x300.png",
    "Washington": "Washington_Huskies_logo-300x300.png",
    "Western Kentucky": "Western_Kentucky_Hilltoppers_logo-300x300.png",
    "Western Michigan": "Western_Michigan_Broncos_logo-300x300.png",
    "West Virginia": "West_Virginia_Mountaineers_logo-300x300.png",
    "Wisconsin": "Wisconsin_Badgers_logo-300x300.png",
    "Wyoming": "Wyoming_Cowboys_logo-300x300.png",
}

# ---------------------------------------------------
# Insert Teams
# ---------------------------------------------------

def main():
    print("=== Seeding all teams from logo_map keys ===")

    with SessionLocal() as s:
        existing = {t.name for t in s.execute(select(Team)).scalars().all()}
        new_names = [name for name in logo_map.keys() if name not in existing]

        for team_name in new_names:
            s.add(Team(name=team_name))

        s.commit()

        print(f"Inserted {len(new_names)} new teams.")
        print("Done ✅")

if __name__ == "__main__":
    main()
