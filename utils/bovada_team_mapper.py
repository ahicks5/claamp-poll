"""
Utility to map Bovada team names to our Team database records.
Uses fuzzy matching and manual mapping table for edge cases.
"""

from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import Team, BovadaTeamMapping

# Manual mappings for known edge cases where Bovada names differ significantly
MANUAL_MAPPINGS = {
    # Bovada name -> Our team name
    "Louisiana-Lafayette": "Louisiana",
    "Louisiana Lafayette": "Louisiana",
    "Louisiana Monroe": "ULM",
    "Louisiana-Monroe": "ULM",
    "UL Monroe": "ULM",
    "UTSA": "UTSA",
    "UAB": "UAB",
    "UCF": "UCF",
    "UCLA": "UCLA",
    "UConn": "UConn",
    "Connecticut": "UConn",
    "UMass": "UMass",
    "Massachusetts": "UMass",
    "UNLV": "UNLV",
    "USC": "USC",
    "Southern California": "USC",
    "UTEP": "UTEP",
    "Miami FL": "Miami (FL)",
    "Miami Hurricanes": "Miami (FL)",
    "Miami": "Miami (FL)",  # Default Miami to FL
    "Miami (Ohio)": "Miami (OH)",
    "Miami OH": "Miami (OH)",
    "Miami RedHawks": "Miami (OH)",
    "Ole Miss": "Ole Miss",
    "Mississippi": "Ole Miss",
    "Miss": "Ole Miss",
    "Pitt": "Pitt",
    "Pittsburgh": "Pitt",
    "SMU": "SMU",
    "Southern Methodist": "SMU",
    "TCU": "TCU",
    "BYU": "BYU",
    "LSU": "LSU",
    "FIU": "FIU",
    "Florida International": "FIU",
    "NC State": "NC State",
    "N.C. State": "NC State",
    "North Carolina State": "NC State",
    "Hawaii": "Hawai'i",
    "Hawai'i": "Hawai'i",
    "San Jose State": "San José State",
    "San José State": "San José State",
    "SJSU": "San José State",
}


def normalize_team_name(name: str) -> str:
    """Normalize team name for better matching"""
    if not name:
        return ""

    # Remove common suffixes and normalize
    normalized = name.strip()

    # Remove mascot names that Bovada might include
    mascots = [
        " Crimson Tide", " Tigers", " Bulldogs", " Wildcats", " Gators",
        " Seminoles", " Buckeyes", " Wolverines", " Sooners", " Longhorns",
        " Trojans", " Fighting Irish", " Ducks", " Huskies", " Cougars",
        " Bears", " Cardinals", " Eagles", " Falcons", " Cowboys",
        " Aggies", " Rebels", " Golden Bears", " Sun Devils", " Tar Heels",
        " Blue Devils", " Yellow Jackets", " Hokies", " Hurricanes",
        " Spartans", " Nittany Lions", " Cornhuskers", " Razorbacks",
        " Volunteers", " Gamecocks", " Terrapins", " Scarlet Knights",
        " Boilermakers", " Hawkeyes", " Golden Gophers", " Badgers",
        " Mountaineers", " Red Raiders", " Horned Frogs", " Cyclones",
        " Jayhawks", " Black Knights", " Midshipmen", " Rainbow Warriors",
        " Broncos", " Rams", " Wolf Pack", " Lobos", " Roadrunners",
        " Mean Green", " Bulls", " Knights", " Owls", " Pirates",
        " Thundering Herd", " 49ers", " Bearcats", " Chanticleers",
        " Ragin' Cajuns", " Ragin Cajuns", " Warhawks", " Flames",
        " Minutemen", " Minutewomen", " Demon Deacons", " Orange",
        " Commodores", " Cavaliers", " Hoosiers", " Illini",
        " Chippewas", " Redhawks", " RedHawks", " Bobcats", " Rockets",
        " Zips", " Cardinals", " Herd", " Hilltoppers", " Jaguars",
        " Panthers", " Bearkats", " Monarchs", " Green Wave",
        " Golden Hurricane", " Golden Eagles", " Mustangs", " Aztecs",
        " Broncos", " Blazers", " Blue Raiders"
    ]

    for mascot in mascots:
        if normalized.endswith(mascot):
            normalized = normalized[:-len(mascot)].strip()
            break

    # Handle "State" variations
    normalized = normalized.replace(" St.", " State")
    normalized = normalized.replace(" St ", " State ")

    # Remove extra whitespace
    normalized = " ".join(normalized.split())

    return normalized


def fuzzy_match_score(s1: str, s2: str) -> float:
    """
    Simple fuzzy matching score between 0 and 1.
    Uses basic edit distance approach.
    """
    s1, s2 = s1.lower(), s2.lower()

    # Exact match
    if s1 == s2:
        return 1.0

    # Check if one contains the other
    if s1 in s2 or s2 in s1:
        return 0.9

    # Calculate Levenshtein-like distance
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    # Use simple character overlap approach for speed
    set1, set2 = set(s1), set(s2)
    overlap = len(set1 & set2)
    total = len(set1 | set2)

    if total == 0:
        return 0.0

    return overlap / total


def map_bovada_team(bovada_name: str, session: Session, confidence_threshold: float = 0.75) -> Optional[Tuple[Team, str]]:
    """
    Map a Bovada team name to our Team record.

    Returns:
        (Team, confidence) where confidence is 'exact', 'fuzzy', or None if no match
    """
    if not bovada_name:
        return None

    # First, check if we already have a cached mapping
    existing = session.execute(
        select(BovadaTeamMapping)
        .where(BovadaTeamMapping.bovada_name == bovada_name)
    ).scalar_one_or_none()

    if existing:
        team = session.get(Team, existing.team_id)
        return (team, existing.confidence) if team else None

    # Check manual mappings
    if bovada_name in MANUAL_MAPPINGS:
        our_name = MANUAL_MAPPINGS[bovada_name]
        team = session.execute(
            select(Team).where(Team.name == our_name)
        ).scalar_one_or_none()

        if team:
            # Cache this mapping
            mapping = BovadaTeamMapping(
                bovada_name=bovada_name,
                team_id=team.id,
                confidence='manual'
            )
            session.add(mapping)
            return (team, 'manual')

    # Try exact match first
    team = session.execute(
        select(Team).where(Team.name == bovada_name)
    ).scalar_one_or_none()

    if team:
        # Cache this mapping
        mapping = BovadaTeamMapping(
            bovada_name=bovada_name,
            team_id=team.id,
            confidence='exact'
        )
        session.add(mapping)
        return (team, 'exact')

    # Try normalized match
    normalized_bovada = normalize_team_name(bovada_name)

    # Get all teams and find best fuzzy match
    all_teams = session.execute(select(Team)).scalars().all()

    best_match = None
    best_score = 0.0

    for team in all_teams:
        normalized_our = normalize_team_name(team.name)
        score = fuzzy_match_score(normalized_bovada, normalized_our)

        if score > best_score:
            best_score = score
            best_match = team

    if best_match and best_score >= confidence_threshold:
        # Cache this fuzzy mapping
        mapping = BovadaTeamMapping(
            bovada_name=bovada_name,
            team_id=best_match.id,
            confidence='fuzzy'
        )
        session.add(mapping)
        return (best_match, 'fuzzy')

    # No good match found
    return None


def get_or_create_mapping(bovada_name: str, our_team_name: str, session: Session) -> BovadaTeamMapping:
    """
    Manually create/update a mapping between Bovada name and our team.
    Useful for admin panel.
    """
    team = session.execute(
        select(Team).where(Team.name == our_team_name)
    ).scalar_one_or_none()

    if not team:
        raise ValueError(f"Team '{our_team_name}' not found in database")

    existing = session.execute(
        select(BovadaTeamMapping)
        .where(BovadaTeamMapping.bovada_name == bovada_name)
    ).scalar_one_or_none()

    if existing:
        existing.team_id = team.id
        existing.confidence = 'manual'
        return existing
    else:
        mapping = BovadaTeamMapping(
            bovada_name=bovada_name,
            team_id=team.id,
            confidence='manual'
        )
        session.add(mapping)
        return mapping
