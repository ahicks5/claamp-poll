import os

def build_logo_map(logos_dir="logos"):
    """
    Scan the logos directory and return a mapping:
        clean_team_name -> actual_filename
    """
    mapping = {}

    if not os.path.isdir(logos_dir):
        raise ValueError(f"Directory not found: {logos_dir}")

    for filename in os.listdir(logos_dir):
        # Skip junk / non-image files
        if filename.lower().startswith("."):
            continue

        if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")):
            continue

        # Remove extension
        name_no_ext = os.path.splitext(filename)[0]

        # Clean up weird symbols
        clean = (
            name_no_ext
            .replace("_", " ")
            .replace("-", " ")
            .strip()
        )

        # Title case (optional)
        clean = " ".join(w.capitalize() for w in clean.split())

        mapping[clean] = filename

    return mapping


# RUN IT
if __name__ == "__main__":
    logos = build_logo_map("logos")
    print(logos)
