#!/usr/bin/env python3

"""
Dumps out your anki database to .jsonl
"""

import sqlite3
import json
import sys
from pathlib import Path


def get_anki_profiles():
    """Get list of Anki user profiles from prefs21.db"""
    prefs_db_path = Path.home() / ".local/share/Anki2/prefs21.db"
    
    if not prefs_db_path.exists():
        return []
    
    try:
        conn = sqlite3.connect(prefs_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM profiles")
        profiles = [row[0] for row in cursor.fetchall()]
        conn.close()
        return profiles
    except Exception as e:
        print(f"Error reading profiles: {e}", file=sys.stderr)
        return []


def get_collection_data(profile_name):
    """Extract data from a profile's collection.anki2 database"""
    collection_path = Path.home() / f".local/share/Anki2/{profile_name}/collection.anki2"
    
    if not collection_path.exists():
        return []
    
    try:
        conn = sqlite3.connect(collection_path)
        cursor = conn.cursor()
        
        # Join tables to get all required data
        query = """
        SELECT 
            d.id as deck_id,
            d.name as deck_name,
            n.id as note_id,
            n.flds as note_flds,
            n.sfld as note_front,
            c.reps,
            c.lapses
        FROM cards c
        JOIN decks d ON c.did = d.id
        JOIN notes n ON c.nid = n.id AND c.ord = 0
        """
        
        cursor.execute(query)
        results = []
        
        for row in cursor.fetchall():
            deck_id, deck_name, note_id, note_flds, note_front, note_reps, note_lapses = row
            
            # Calculate note_back by removing the front part from flds
            front_length = len(note_front) if note_front else 0
            note_back = note_flds[front_length+1:] if note_flds and front_length < len(note_flds) else ""
            
            results.append({
                "profile": profile_name,
                "deck_id": deck_id,
                "deck_name": deck_name,
                "note_id": note_id,
                "note_front": note_front or "",
                "note_back": note_back,
                "note_reps": note_reps,
                "note_lapses": note_lapses
            })
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"Error reading collection for profile {profile_name}: {e}", file=sys.stderr)
        return []


def main():
    """Main function to export Anki data to JSONL format"""
    profiles = get_anki_profiles()
    
    if not profiles:
        print("No Anki profiles found", file=sys.stderr)
        return
    
    for profile in profiles:
        collection_data = get_collection_data(profile)
        
        for record in collection_data:
            print(json.dumps(record))


if __name__ == "__main__":
    main()
